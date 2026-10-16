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
"""
from .. import ir as I
from .. import effects as E
from . import simplify

RESIZING = ('list.push', 'list.pop', 'list.clear', 'ba.push', 'ba.clear', 'ba.extend_lit')
# S3a: operations that replace or grow the list they name (the first operand; both for a move)
REPLACING = ('list.reset', 'list.repeat', 'list.lit', 'list.reserve', 'list.move', 'list.call')


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
    d = defs.get(v)
    if d is not None and d.op == 'const':
        c = d.attrs.get('value')
        if isinstance(c, int) and not isinstance(c, bool):
            return c
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
            refs = ins.operands[:2] if ins.op == 'list.move' else ins.operands[:1]
            return any(E._root(r, self.fn, defs) in (root, 'Any') for r in refs)
        return False

    def resizes(self, ins):
        if ins.op in RESIZING or ins.op in REPLACING:
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

    def hoist_pure(self, loop):
        inside = _inside(loop)
        defs = _defs(self.fn)
        moved = []

        def visit(region):
            keep = []
            for ins in region.instrs:
                if (not ins.regions and ins.op != 'const' and simplify.is_pure(ins, defs)
                        and all(v not in inside for v in ins.operands)):
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
        any_resize = None
        lists = []
        for ins in body:
            if ins.op in ('list.get', 'list.set', 'list.len', 'ba.get', 'ba.set', 'ba.len'):
                L = ins.operands[0]
                if L in inside or L in lists:
                    continue
                root = E._root(L, self.fn, defs)
                if root.startswith('Own('):
                    # an owned list: only an operation naming this very list can resize it
                    if any(self.resizes_root(i, root, defs) for i in body):
                        continue
                else:
                    if any_resize is None:
                        any_resize = any(self.resizes(i) for i in body)
                    if any_resize:
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
        if d is None or d.op not in ('add', 'sub'):
            return None
        a, b = d.operands
        if d.op == 'add' and a is idx and _const(b, defs) is not None:
            c = _const(b, defs)
        elif d.op == 'add' and b is idx and _const(a, defs) is not None:
            c = _const(a, defs)
        elif d.op == 'sub' and a is idx and _const(b, defs) is not None:
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
            if d.op.startswith('cmp.') and d.operands[0].type == I.I64:
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
            if pred not in ('lt', 'le') or a not in body.args or b in inside:
                continue
            k = body.args.index(a)
            if all(self.non_decreasing(e.operands[k], a, defs) for e in own):
                return a, loop.operands[k], b, pred == 'lt', test
        return None

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
        idx = lo = hi = None
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
                idx, lo, hi, strict, test = found
                scope = loop.regions[0].instrs[test + 1:]
        ranges = {}           # container -> [cmin, cmax]
        absolute = {}         # container -> largest index known from the range pass (index >= 0)
        facts = getattr(self.fn, 'index_facts', {})
        accesses = []
        for ins in (i for top in scope for i in I.walk(I.Region([], [top]))):
            if ins.op in ('span.get', 'span.set', 'bytes.get'):
                base, index = ins.operands[0], ins.operands[1]
                if base in inside:
                    continue
                c = self.index_offset(index, idx, defs) if idx is not None else None
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
        if not accesses:
            return None
        # containers whose accesses are already proven join the guard too (as the legacy path's
        # guard does): in the fast copy their bounds then imply the loop's own tests
        ranges = dict((b, r) for b, r in ranges.items()
                      if any(a.operands[0] is b for a in accesses) or len(ranges) <= 4)
        if not ranges and not absolute:
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
        for base, (cmin, cmax) in ranges.items():
            n = emit('span.len' if base.type.head == 'span' else 'bytes.len', [base], I.I64)
            conds.append(emit('cmp.ge', [lo, emit('const', [], I.I64, {'value': -cmin})], I.I1))
            limit = emit('sub', [n, emit('const', [], I.I64, {'value': cmax})], I.I64, {'mode': 'nsw'})
            conds.append(emit('cmp.le' if strict else 'cmp.lt', [hi, limit], I.I1))
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
