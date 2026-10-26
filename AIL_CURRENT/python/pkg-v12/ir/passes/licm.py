"""Loop-invariant code motion, list header hoisting and loop versioning (design §3.6, §3.2).

1. **Pure LICM.** An instruction that cannot fail, write or read mutable memory, and whose
   operands are all defined outside a loop, moves in front of the loop (e.g. the address of a
   struct's list field, `len()` of a bytes view, a constant expression).
2. **Span hoisting.** In a loop that contains nothing that can resize or replace a list (no
   push/pop/clear, no call whose summary is unknown or writes a list), every list reached from
   outside the loop is read through a `span` -- its data pointer and length loaded once in front
   of the loop -- so the C compiler keeps them in registers (a store through the data pointer
   could otherwise alias the length). The legacy path does the same per loop
   ("span-cached field lists"); here it applies to any loop nest at the outermost stable loop.
3. **Versioning.** A `for.range` loop with step 1 whose body indexes spans or bytes defined
   outside it at `i + c` (constant c) gets a guard in front of it:
   `lo >= -cmin and hi <= len - cmax` for every such container; when it holds, a copy of the
   loop with those accesses unchecked runs, otherwise the original loop (so an out-of-range
   access still fails at the same iteration, after the same effects, with the same message).
   The legacy path versions innermost loops only; this pass also versions outer loops (the
   accesses of an outer index inside inner loops). The slow copy is never versioned again, so
   code grows at most linearly with nesting depth.
   An access whose index is not `i + c` joins the guard through symbolic bounds (symbounds.py):
   `cur[up + x]`, `cur[mid + xl[x]]` with `up`, `mid` invariant, x the index of an inner loop and
   xl a list whose stored values all lie in [0, w - 1] give `up >= 0 and up + w - 1 < len(cur)`, etc.
   A byte store proven in range this way keeps only its value check (mode `vck`).

A bytearray local (a place) is read with `load` inside the loop; that load is invariant when
nothing in the loop names the place except loads and the place holds a bytearray wherever the loop
starts, so it moves in front of the loop and the bytearray gets a span like a list.
"""
from .. import ir as I
from .. import effects as E
from . import simplify, symbounds

RESIZING = ('list.push', 'list.pop', 'list.clear', 'rec.push', 'rec.pop', 'ba.push', 'ba.clear', 'ba.extend_lit')
# what can resize a bytearray (whose span a loop may now hold: a bytearray local's load is hoisted)
BA_RESIZING = ('ba.push', 'ba.clear', 'ba.extend_lit', 'ba.extend')
U8SPAN = I.T('span', I.T('u8'))
# S3a: operations that replace or grow the list they name (the first operand; both for a move)
REPLACING = ('list.reset', 'list.repeat', 'list.lit', 'list.reserve', 'list.move', 'list.call', 'list.copy',
             'list.rt', 'list.sortperm')


def _defs(fn):
    return {r: ins for ins in I.walk(fn.body) for r in ins.results}


def _inside(loop):
    out = set()
    for r in loop.regions:
        out.update(r.args)
        for ins in I.walk(r):
            out.update(ins.results)
            for sub in ins.regions:
                out.update(sub.args)
    return out


def _const(v, defs):
    for _ in range(8):
        d = defs.get(v)
        if d is not None and d.op in ('tint.from', 'tint.i64', 'tint.i64sat'):
            v = d.operands[0]
            continue
        if d is not None and d.op == 'const':
            c = d.attrs.get('value')
            if isinstance(c, int) and not isinstance(c, bool):
                return c
        return None
    return None


class Cloner(object):
    def __init__(self):
        self.vmap = {}
        self.imap = {}

    def value(self, v):
        return self.vmap.get(v, v)

    def instr(self, ins):
        new = I.Instr(ins.op, [self.value(v) for v in ins.operands], [], dict(ins.attrs), [])
        new.regions = [self.region(r) for r in ins.regions]
        for r in ins.results:
            nv = I.Value(r.type, r.hint)
            self.vmap[r] = nv
            new.results.append(nv)
        self.imap[ins] = new
        if id(ins) in I.SRC:
            I.SRC[id(new)] = (new, I.SRC[id(ins)][1])
        return new

    def region(self, region):
        args = []
        for a in region.args:
            na = I.Value(a.type, a.hint)
            self.vmap[a] = na
            args.append(na)
        return I.Region(args, [self.instr(i) for i in region.instrs])


class LICM(object):
    def __init__(self, fn, summaries=None):
        self.fn = fn
        self.summaries = summaries or {}
        self.hoisted = 0
        self.spans = 0
        self.versioned = 0
        self.frozen = set()          # loops never to version (slow copies)

    # ------------------------------------------------------------------ helpers
    def resizes_root(self, ins, root, defs):
        """Whether `ins` may resize or replace the owned list rooted at `root` (a list the function
        owns: only an operation naming that very list can; a call has no way to name it)."""
        if ins.op in RESIZING:
            return E._root(ins.operands[0], self.fn, defs) in (root, 'Any')
        if ins.op in REPLACING:
            refs = ins.operands[:2] if ins.op in ('list.move', 'list.copy') else ins.operands[:1]
            return any(E._root(r, self.fn, defs) in (root, 'Any') for r in refs)
        return False

    def resizes(self, ins, kind='list'):
        """Whether `ins` may resize or replace a list (kind 'list': the rule the list spans have always
        used), or a bytearray (kind 'bytearray': a bytearray operation that grows or clears one, or a
        call that may)."""
        if kind == 'bytearray':
            if ins.op in BA_RESIZING:
                return True
        elif ins.op in RESIZING or ins.op in REPLACING:
            return True
        if ins.op == 'call':
            eff = self.summaries.get(ins.attrs.get('callee'))
            if eff is None or eff.unknown:
                return True
            return any(w.startswith('Spine(') for w in eff.writes)
        return False

    def regions_of(self, region):
        """(region, instr index) pairs are edited in place: walk loops in pre-order."""
        for k, ins in enumerate(list(region.instrs)):
            yield region, ins
            for r in ins.regions:
                for item in self.regions_of(r):
                    yield item

    # ------------------------------------------------------------------ 1. pure LICM
    def pure_licm(self, region):
        k = 0
        while k < len(region.instrs):
            ins = region.instrs[k]
            for r in ins.regions:
                self.pure_licm(r)
            if ins.op in I.LOOP_OPS:
                moved = self.hoist_pure(ins)
                region.instrs[k:k] = moved
                k += len(moved)
            k += 1

    def initialised_before(self, loop):
        """Object places given an object by a top-level instruction of the body that precedes the
        top-level statement holding `loop` (so they hold one wherever the loop starts)."""
        out = set()
        for top in self.fn.body.instrs:
            if top is loop or any(i is loop for r in top.regions for i in I.walk(r)):
                return out
            if top.op in ('obj.init', 'obj.copyref') or (top.op == 'store' and top.operands[0].type.pointee.head == 'obj'):
                out.add(top.operands[0])
        return set()

    def bytearrays_held(self, loop, defs):
        """Bytearray places that hold a bytearray wherever `loop` starts and never stop holding one:
        given a fresh one (`ba.new`) by a top-level instruction before the statement holding `loop`,
        and otherwise only ever given one by `ba.new` or by `ba.copyref` of the load of another such
        place (no `ba.drop`, no `ba.call`, no other instruction naming the place). Their loads may be
        read early, and a span over them taken, in front of the loop."""
        first = set()
        for top in self.fn.body.instrs:
            if top is loop or any(i is loop for r in top.regions for i in I.walk(r)):
                break
            if top.op == 'ba.new':
                first.add(top.operands[0])
        else:
            return set()
        held = set(first)
        BA = I.T('obj', I.T('bytearray'))

        def places(ins):
            return [v for v in ins.operands if v.type.is_place and v.type.pointee == BA]

        def scan(region, fresh, bad, loads):
            """`fresh`: places that certainly hold a bytearray at this point of the region (given one
            earlier in straight-line code: `tmp = cur; cur = nxt; nxt = tmp`). Adds to `bad` every
            held place some instruction may leave without one."""
            fresh = set(fresh)
            loads = dict(loads)
            for ins in region.instrs:
                if ins.op == 'load':
                    if places(ins):
                        loads[ins.result] = ins.operands[0] in held or ins.operands[0] in fresh
                    continue
                if ins.regions:
                    inner = set()
                    for r in ins.regions:
                        scan(r, fresh, bad, loads)
                        for i in I.walk(r):
                            if i.op != 'load':
                                inner.update(places(i))
                    fresh -= inner
                named = places(ins)
                if not named:
                    continue
                if ins.op == 'ba.new' and named == [ins.operands[0]]:
                    fresh.add(ins.operands[0])
                    continue
                if ins.op == 'ba.copyref' and named == [ins.operands[0]] and loads.get(ins.operands[1]):
                    fresh.add(ins.operands[0])
                    continue
                fresh.difference_update(named)
                bad.update(v for v in named if v in held)
        while True:
            bad = set()
            scan(self.fn.body, set(), bad, {})
            if not bad:
                return held
            held -= bad

    def global_unchanged_in(self, loop, name, defs):
        """Whether nothing in `loop` can store the module variable `name`: no `global.store` of it and
        no call whose summary may write it (a call without a summary may write anything)."""
        loc = 'Global(m,%s)' % name
        for r in loop.regions:
            for i in I.walk(r):
                eff = E.instr_effects(i, self.fn, None, None, defs, self.summaries)
                if eff.unknown or loc in eff.writes:
                    return False
        return True

    def hoist_pure(self, loop):
        inside = _inside(loop)
        defs = _defs(self.fn)
        moved = []
        # The place of a struct local (the object pointer) changes only through an instruction naming it
        # (`store`, `obj.init`, `obj.copyref`): a call cannot reach a local place. Its `load` is
        # invariant in a loop that names the place in nothing but loads, so the field lists read
        # through it get spans as those of a struct parameter do. Only a place that already holds an
        # object where the loop starts (initialised at the top level of the body, before the
        # statement holding the loop) is read early: a span over the field of no object would fault
        # in front of a loop that runs no iteration.
        named = set()
        for r in loop.regions:
            for i in I.walk(r):
                if i.op != 'load':
                    named.update(v for v in i.operands if v.type.is_place)
        ready = self.initialised_before(loop)
        held = None

        def invariant_load(ins):
            nonlocal held
            if ins.op != 'load':
                return False
            p = ins.operands[0]
            t = p.type.pointee
            if p in named or t.head != 'obj':
                return False
            if t.args[0].head == 'class':
                return p in ready
            if t.args[0].head == 'bytearray':
                # only where the bytearray then gets a span (nothing in the loop can resize one):
                # elsewhere the early load only holds a register across the loop's calls
                if held is None:
                    stable = not any(self.resizes(i, 'bytearray') for r in loop.regions for i in I.walk(r))
                    held = self.bytearrays_held(loop, defs) if stable else set()
                return p in held
            return False

        first_load = {}           # place -> the result of its first invariant load moved out
        renames = {}

        def visit(region):
            keep = []
            for ins in region.instrs:
                if (not ins.regions and ins.op != 'const' and (simplify.is_pure(ins, defs) or invariant_load(ins) or (
                        ins.op == 'global.load' and self.global_unchanged_in(loop, ins.attrs['name'], defs)))
                        and all(v not in inside for v in ins.operands)):
                    if ins.op == 'load':
                        # every load of the place reads the same object or bytearray in this loop: one
                        # is enough (one span, not one per read)
                        p = ins.operands[0]
                        if p in first_load:
                            renames[ins.result] = first_load[p]
                            inside.discard(ins.result)
                            continue
                        first_load[p] = ins.result
                    moved.append(ins)
                    for r in ins.results:
                        inside.discard(r)
                    continue
                for r in ins.regions:
                    visit(r)
                keep.append(ins)
            region.instrs = keep
        for r in loop.regions:
            visit(r)
        if renames:
            for ins in list(I.walk(self.fn.body)) + moved:
                ins.operands = [renames.get(v, v) for v in ins.operands]
        self.hoisted += len(moved)
        return moved

    # ------------------------------------------------------------------ 2. spans
    def span_hoist(self, region):
        k = 0
        while k < len(region.instrs):
            ins = region.instrs[k]
            if ins.op in I.LOOP_OPS:
                new = self.make_spans(ins)
                region.instrs[k:k] = new
                k += len(new)
                ins = region.instrs[k]
            for r in ins.regions:
                self.span_hoist(r)
            k += 1

    def make_spans(self, loop):
        inside = _inside(loop)
        defs = _defs(self.fn)
        body = [i for r in loop.regions for i in I.walk(r)]
        any_resize = {}
        lists = []
        for ins in body:
            if ins.op in ('list.get', 'list.set', 'list.len', 'ba.get', 'ba.set', 'ba.len'):
                L = ins.operands[0]
                if L in inside or L in lists:
                    continue
                if L.type.args[0].head == 'list' and L.type.args[0].args[0] not in (I.I64, I.F64):
                    continue                 # a list of str has no span (S3c-1)
                root = E._root(L, self.fn, defs)
                if root.startswith('Own('):
                    # an owned list: only an operation naming this very list can resize it
                    if any(self.resizes_root(i, root, defs) for i in body):
                        continue
                else:
                    kind = L.type.args[0].head
                    if kind not in any_resize:
                        any_resize[kind] = any(self.resizes(i, kind) for i in body)
                    if any_resize[kind]:
                        continue
                lists.append(L)
        if not lists:
            return []
        made = []
        span_of = {}
        for L in lists:
            elem = I.T('u8') if L.type.args[0].head == 'bytearray' else L.type.args[0].args[0]
            sp = I.Instr('span.of', [L], [I.Value(I.T('span', elem))])
            made.append(sp)
            span_of[L] = sp.result
        for r in loop.regions:
            for ins in I.walk(r):
                if ins.op in ('list.get', 'list.set', 'list.len', 'ba.get', 'ba.set', 'ba.len') \
                        and ins.operands[0] in span_of:
                    ins.op = 'span.' + ins.op.split('.', 1)[1]
                    ins.operands[0] = span_of[ins.operands[0]]
        self.spans += len(made)
        return made

    # ------------------------------------------------------------------ 3. versioning
    def version_all(self, region):
        k = 0
        while k < len(region.instrs):
            ins = region.instrs[k]
            if ins.op in I.LOOP_OPS and ins not in self.frozen:
                new = self.version(ins)
                if new is not None:
                    region.instrs[k:k + 1] = new
                    fast = new[-1].regions[0]
                    self.version_all(fast)          # inner loops of the fast copy
                    k += len(new)
                    continue
            for r in ins.regions:
                self.version_all(r)
            k += 1

    def index_offset(self, v, idx, defs):
        if v is idx:
            return 0
        d = defs.get(v)
        if d is None:
            return None
        if d.op in ('tint.from', 'tint.i64', 'tint.i64sat'):
            return self.index_offset(d.operands[0], idx, defs)
        op = d.op
        if op.startswith('tint.'):
            op = op[5:]
            if op.endswith('_i64'):
                op = op[:-4]
        if op not in ('add', 'sub'):
            return None
        a, b = d.operands
        if op == 'add' and a is idx and _const(b, defs) is not None:
            c = _const(b, defs)
        elif op == 'add' and b is idx and _const(a, defs) is not None:
            c = _const(a, defs)
        elif op == 'sub' and a is idx and _const(b, defs) is not None:
            c = -_const(b, defs)
        else:
            return None
        return c if abs(c) <= (1 << 20) else None

    def induction(self, loop, defs, inside):
        """For a `loop` (a while loop): (index arg, its value before the loop, bound, strict,
        position of the loop test) when the body starts with the lowering's test
        `if c {yield} {break}`, `c` implies `i < hi` (or `i <= hi`) for a carried `i` and a `hi`
        defined outside, and every `continue` passes `i` or `i + k` (k >= 0): then every
        instruction after the test sees lo <= i < hi (<= hi)."""
        body = loop.regions[0]
        test = None
        for t, ins in enumerate(body.instrs):
            if ins.op == 'if' and not ins.results and [r.instrs[-1].op for r in ins.regions] == ['yield', 'break'] \
                    and len(ins.regions[0].instrs) == 1 and len(ins.regions[1].instrs) == 1:
                test = t
                break
        if test is None:
            return None

        def atoms(v, depth=0):
            d = defs.get(v)
            if d is None or depth > 6:
                return []
            if d.op.startswith('cmp.') and d.operands[0].type == I.I64 and d.operands[1].type == I.I64:
                return [(d.op[4:], d.operands[0], d.operands[1])]
            if d.op == 'if' and len(d.results) == 1:
                ty, oy = d.regions[0].instrs[-1], d.regions[1].instrs[-1]
                if ty.op == 'yield' and oy.op == 'yield' and defs.get(oy.operands[0]) is not None \
                        and defs[oy.operands[0]].op == 'const' and defs[oy.operands[0]].attrs.get('value') is False:
                    return atoms(d.operands[0], depth + 1) + atoms(ty.operands[0], depth + 1)
            return []
        own = [e for e in self.exits(loop) if e.op == 'continue']
        for pred, a, b in atoms(body.instrs[test].operands[0]):
            if pred in ('gt', 'ge'):
                pred, a, b = {'gt': 'lt', 'ge': 'le'}[pred], b, a
            if pred not in ('lt', 'le') or a not in body.args:
                continue
            k = body.args.index(a)
            if not all(self.non_decreasing(e.operands[k], a, defs) for e in own):
                continue
            if b not in inside:
                return a, loop.operands[k], b, pred == 'lt', test, None
            # two pointers closing in on each other (`while a < b: ...; a += 1; b -= 1`): b is carried and
            # never increases, so a < b <= b0 (its value before the loop) in every iteration
            if b in body.args:
                kb = body.args.index(b)
                if all(self.non_increasing(e.operands[kb], b, defs) for e in own):
                    return a, loop.operands[k], loop.operands[kb], pred == 'lt', test, b
        return None

    @staticmethod
    def non_increasing(v, a, defs):
        if v is a:
            return True
        d = defs.get(v)
        if d is None or d.op not in ('add', 'sub'):
            return False
        x, y = d.operands
        if d.op == 'sub':
            c = _const(y, defs) if x is a else None
            return c is not None and c >= 0
        other = y if x is a else x if y is a else None
        c = _const(other, defs) if other is not None else None
        return c is not None and c <= 0

    @staticmethod
    def non_decreasing(v, a, defs):
        if v is a:
            return True
        d = defs.get(v)
        if d is None or d.op != 'add':
            return False
        x, y = d.operands
        other = y if x is a else x if y is a else None
        c = _const(other, defs) if other is not None else None
        return c is not None and c >= 0

    def exits(self, loop):
        out = []

        def walk(region):
            for ins in region.instrs:
                if ins.op in ('break', 'continue'):
                    out.append(ins)
                if ins.op == 'if':
                    for r in ins.regions:
                        walk(r)
        walk(loop.regions[0])
        return out

    def version(self, loop):
        defs = _defs(self.fn)
        idx = lo = hi = dec = None
        strict = True
        scope = loop.regions[0].instrs
        inside = _inside(loop)
        if loop.op == 'for.range':
            lo, hi, step = loop.operands[:3]
            if _const(step, defs) == 1:
                idx = loop.regions[0].args[0]
        else:
            found = self.induction(loop, defs, inside)
            if found is not None:
                idx, lo, hi, strict, test, dec = found
                scope = loop.regions[0].instrs[test + 1:]
        ranges = {}           # container -> [cmin, cmax]
        down = {}             # container -> [cmin, cmax] of the accesses at the closing pointer `dec + c`
        absolute = {}         # container -> largest index known from the range pass (index >= 0)
        facts = getattr(self.fn, 'index_facts', {})
        accesses = []
        sym = {}              # container -> [(lows, highs, conds)] of the accesses with symbolic bounds
        byte_stores = []      # byte stores among them (their value check stays: mode vck)
        bounds = None
        for ins in (i for top in scope for i in I.walk(I.Region([], [top]))):
            if ins.op in ('span.get', 'span.set', 'bytes.get'):
                base, index = ins.operands[0], ins.operands[1]
                if base in inside:
                    continue
                c = self.index_offset(index, idx, defs) if idx is not None else None
                if c is None and dec is not None:
                    c2 = self.index_offset(index, dec, defs)
                    if c2 is not None:
                        lohi = down.setdefault(base, [c2, c2])
                        lohi[0], lohi[1] = min(lohi[0], c2), max(lohi[1], c2)
                        if ins.attrs.get('mode') == 'ck' and not (
                                ins.op == 'span.set' and base.type == I.T('span', I.T('u8'))):
                            accesses.append(ins)
                        continue
                if c is None and ins.attrs.get('mode') == 'ck':
                    if bounds is None:
                        order = symbounds.value_order(self.fn)
                        elements = symbounds.ElementFacts(self.fn, defs, order).for_loop(loop)
                        bounds = symbounds.Bounds(self.fn, inside, defs, order, elements)
                    b = bounds.of(index)
                    if b is not None and all(f.terms or f.const >= 0 for f in b[0]) \
                            and all(f.terms or f.const >= 0 for f in b[2]):
                        sym.setdefault(base, []).append(b)
                        if ins.op == 'span.set' and base.type == U8SPAN:
                            byte_stores.append(ins)
                        else:
                            accesses.append(ins)
                        continue
                if c is None:
                    span = facts.get(ins)
                    if (ins.attrs.get('mode') == 'ck' and span is not None and span[0] >= 0
                            and span[1] < (1 << 40) and not (ins.op == 'span.set'
                                                             and base.type == I.T('span', I.T('u8')))):
                        absolute[base] = max(absolute.get(base, -1), span[1])
                        accesses.append(ins)
                    continue
                lohi = ranges.setdefault(base, [c, c])
                lohi[0], lohi[1] = min(lohi[0], c), max(lohi[1], c)
                if ins.attrs.get('mode') == 'ck' and not (
                        ins.op == 'span.set' and base.type == I.T('span', I.T('u8'))):
                    accesses.append(ins)       # (a byte store keeps its value check)
        if not accesses and not byte_stores:
            return None
        # containers whose accesses are already proven join the guard too (as the legacy path's
        # guard does): in the fast copy their bounds then imply the loop's own tests
        ranges = dict((b, r) for b, r in ranges.items()
                      if any(a.operands[0] is b for a in accesses) or len(ranges) <= 4)
        if not ranges and not absolute and not down and not sym:
            return None
        pre = []

        def emit(op, operands, t, attrs=None):
            ins = I.Instr(op, operands, [I.Value(t)] if t is not None else [], attrs or {})
            pre.append(ins)
            return ins.results[0] if t is not None else None

        conds = []
        for base, top in absolute.items():
            n = emit('span.len' if base.type.head == 'span' else 'bytes.len', [base], I.I64)
            conds.append(emit('cmp.lt', [emit('const', [], I.I64, {'value': top}), n], I.I1))
        # one lower bound on `lo` and, per container, one upper bound on `hi`: every access gives a
        # threshold, and the strictest of them implies the others
        lower = None
        upper = {}
        for base, (cmin, cmax) in ranges.items():
            need = -cmin
            lower = need if lower is None else max(lower, need)
            k = cmax if strict else cmax + 1              # hi <= len - k
            upper[base] = max(upper.get(base, k), k)
        for base, (cmin, cmax) in down.items():
            # b <= b0 and b > a >= a0 in every iteration: b + c is in range when b0 + cmax < len and
            # a0 + (1 if a < b else 0) + cmin >= 0
            need = -cmin - (1 if strict else 0)
            lower = need if lower is None else max(lower, need)
            upper[base] = max(upper.get(base, cmax + 1), cmax + 1)
        if lower is not None:
            c = emit('const', [], I.I64, {'value': lower})
            if lo.type == I.TINT:
                # lo >= lower, as a tint comparison (`tint.le` takes two tints)
                conds.append(emit('tint.le', [emit('tint.from', [c], I.TINT), lo], I.I1))
            else:
                conds.append(emit('cmp.ge', [lo, c], I.I1))
        for base, k in upper.items():
            n = emit('span.len' if base.type.head == 'span' else 'bytes.len', [base], I.I64)
            limit = emit('sub', [n, emit('const', [], I.I64, {'value': k})], I.I64, {'mode': 'nsw'})
            if hi.type == I.TINT:
                conds.append(emit('tint.le_i64', [hi, limit], I.I1))
            else:
                conds.append(emit('cmp.le', [hi, limit], I.I1))
        if sym:
            conds.extend(self.symbolic_guard(sym, emit))
        guard = conds[-1]
        for c in reversed(conds[:-1]):
            # c and guard, as the lowering builds `and` (the range pass reads this shape)
            then = I.Region([], [I.Instr('yield', [guard])])
            other = I.Region([], [I.Instr('const', [], [I.Value(I.I1)], {'value': False})])
            other.instrs.append(I.Instr('yield', [other.instrs[0].result]))
            ins = I.Instr('if', [c], [I.Value(I.I1)], {}, [then, other])
            pre.append(ins)
            guard = ins.result
        cl = Cloner()
        fast = cl.instr(loop)
        for a in accesses:
            cl.imap[a].attrs['mode'] = 'nck'
        for a in byte_stores:
            cl.imap[a].attrs['mode'] = 'vck'
        results = [I.Value(r.type, r.hint) for r in loop.results]
        fast_region = I.Region([], [fast, I.Instr('yield', list(fast.results))])
        slow_region = I.Region([], [loop, I.Instr('yield', list(loop.results))])
        choose = I.Instr('if', [guard], results, {}, [fast_region, slow_region])
        self.replace_uses(loop, results)
        self.frozen.add(loop)
        for ins in I.walk(loop.regions[0]):
            if ins.op in I.LOOP_OPS:
                self.frozen.add(ins)
        self.versioned += 1
        return pre + [choose]

    @staticmethod
    def symbolic_guard(sym, emit):
        """The conditions for the accesses with symbolic bounds (symbounds.py): every atom within
        +-ATOM_MAX (so the forms, computed with wrapping arithmetic, are exact), every side condition
        and lower form >= 0, every upper form < the container's length. Each distinct condition once,
        in a deterministic order."""
        consts = {}

        def const(c):
            if c not in consts:
                consts[c] = emit('const', [], I.I64, {'value': c})
            return consts[c]
        values = {}
        shadows = {}

        def atom_i64(a):
            if a.type != I.TINT:
                return a
            if id(a) not in shadows:
                shadows[id(a)] = emit('tint.i64sat', [a], I.I64)
            return shadows[id(a)]

        def value(f):
            key = (f.sig, f.const)
            if key in values:
                return values[key]
            acc = None
            for m, k in f.terms:
                t = atom_i64(m[0])
                for a in m[1:]:
                    t = emit('mul', [t, atom_i64(a)], I.I64, {'mode': 'wrap'})
                if k != 1:
                    t = emit('mul', [t, const(k)], I.I64, {'mode': 'wrap'})
                acc = t if acc is None else emit('add', [acc, t], I.I64, {'mode': 'wrap'})
            if acc is None:
                acc = const(f.const)
            elif f.const:
                acc = emit('add', [acc, const(f.const)], I.I64, {'mode': 'wrap'})
            values[key] = acc
            return acc
        atoms, seen_atoms = [], set()
        nonneg, below = [], []            # forms that must be >= 0; (form, container) that must be < len
        seen_nonneg, seen_below = set(), set()
        for base, items in sym.items():
            for lows, highs, side in items:
                for f in lows + side:
                    for a in f.atoms:
                        if id(a) not in seen_atoms:
                            seen_atoms.add(id(a))
                            atoms.append(a)
                    if f.terms and (f.sig, f.const) not in seen_nonneg:
                        seen_nonneg.add((f.sig, f.const))
                        nonneg.append(f)
                for f in highs:
                    for a in f.atoms:
                        if id(a) not in seen_atoms:
                            seen_atoms.add(id(a))
                            atoms.append(a)
                    if (id(base), f.sig, f.const) not in seen_below:
                        seen_below.add((id(base), f.sig, f.const))
                        below.append((f, base))
        squared = set()
        for f in nonneg + [f for f, _ in below]:
            for m, _ in f.terms:
                if len(m) > 1:
                    squared.update(id(a) for a in m)
        conds = []
        for a in atoms:
            top = symbounds.ATOM2_MAX if id(a) in squared else symbounds.ATOM_MAX
            ac = atom_i64(a)
            conds.append(emit('cmp.le', [ac, const(top)], I.I1))
            conds.append(emit('cmp.ge', [ac, const(-top)], I.I1))
        for f in nonneg:
            conds.append(emit('cmp.ge', [value(f), const(0)], I.I1))
        lens = {}
        for f, base in below:
            if id(base) not in lens:
                lens[id(base)] = emit('span.len' if base.type.head == 'span' else 'bytes.len', [base], I.I64)
            conds.append(emit('cmp.lt', [value(f), lens[id(base)]], I.I1))
        return conds

    def replace_uses(self, loop, results):
        m = dict(zip(loop.results, results))
        if not m:
            return
        own = set(id(i) for i in I.walk(loop.regions[0])) | {id(loop)}
        for ins in I.walk(self.fn.body):
            if id(ins) in own or ins.op == 'yield' and any(v in m for v in ins.operands) and \
                    self._yields_loop(ins, loop):
                continue
            ins.operands = [m.get(v, v) for v in ins.operands]

    @staticmethod
    def _yields_loop(ins, loop):
        return list(ins.operands) == list(loop.results)


def run(fn, summaries=None):
    """Returns {'hoisted', 'spans', 'versioned'}."""
    licm = LICM(fn, summaries)
    licm.pure_licm(fn.body)
    simplify.run(fn)
    licm.span_hoist(fn.body)
    licm.pure_licm(fn.body)
    licm.version_all(fn.body)
    if licm.versioned:
        simplify.run(fn)
        licm.pure_licm(fn.body)
    return {'hoisted': licm.hoisted, 'spans': licm.spans, 'versioned': licm.versioned}
