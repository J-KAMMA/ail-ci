"""Constant folding, branch folding and dead-code elimination on SSA (design §3: SCCP/GVN/DCE).

* Folding: an op whose operands are constants and that cannot raise on them (no overflow, no
  division by zero) becomes a constant; `select` and `if` on a constant condition take the arm
  (an `if` arm that ends in `yield` is spliced in place; one that ends in another terminator is
  spliced and ends the enclosing region).
* Dead code: an instruction that cannot raise, write, call or transfer control and whose results
  are unused is removed; unused `if` results drop their `yield` operands; a loop-carried value
  that is used only to carry itself (and whose loop result is unused) is removed with its initial
  value, block argument, `continue`/`break` operands and result.
* Common subexpressions: within one region and its nested regions, a second pure instruction
  with the same op, operands and attributes reuses the first one's result (GVN over the dominator
  tree of structured regions: an instruction dominates everything after it in its region).

Every step preserves what the program prints and how it fails: an op that may raise is never
removed, folded into a different failure, or moved.
"""
from .. import ir as I
from .. import rtc

_MASK = (1 << 64) - 1
_PURE = {'const', 'str.lit', 'bytes.lit', 'and', 'or', 'xor', 'inv', 'fneg', 'zext', 'sitofp', 'select', 'fadd', 'fsub', 'fmul',
         'cmp.eq', 'cmp.ne', 'cmp.lt', 'cmp.le', 'cmp.gt', 'cmp.ge'}
_MODE_PURE = {'add', 'sub', 'mul', 'neg', 'shl', 'shr'}     # pure unless mode == 'ck'


def may_raise_or_effect(ins, defs=None):
    op = ins.op
    if op in _PURE:
        return False
    if op in _MODE_PURE:
        return ins.attrs.get('mode') == 'ck'
    if op in ('floordiv', 'floormod') and ins.attrs.get('mode') == 'nonneg':
        return False
    if op in ('floordiv', 'floormod') and defs is not None:
        d = _const(ins.operands[1], defs)
        return not (isinstance(d, int) and not isinstance(d, bool) and d not in (0, -1))
    if op in ('fdiv', 'ffloordiv', 'ffloormod') and defs is not None:
        d = _const(ins.operands[1], defs)
        return not (isinstance(d, float) and d != 0.0)
    if op in ('bytes.len', 'field.list', 'span.len', 'list.ref'):
        return False
    if op == 'bytes.get':
        return ins.attrs.get('mode') != 'nck'
    if op == 'fpow':
        return False
    if op == 'rt':
        return not rtc.is_pure(ins.attrs.get('callee'))
    return True


def is_pure(ins, defs=None):
    """No effect and no read of mutable memory: may be CSE'd and removed."""
    return not ins.regions and not may_raise_or_effect(ins, defs)


_READS = ('field.get', 'span.of', 'field.ba')


def removable(ins, defs=None):
    """Unused, it may be deleted: pure, or a read that cannot fail."""
    if is_pure(ins, defs):
        return True
    if ins.regions:
        return False
    if ins.op in _READS:
        return True
    if ins.op in ('list.get', 'span.get') and ins.attrs.get('mode') == 'nck':
        return True
    return False


def _const(v, defs):
    ins = defs.get(v)
    if ins is not None and ins.op == 'const':
        return ins.attrs.get('value')
    return None


def _s64(x):
    x &= _MASK
    return x - (1 << 64) if x >> 63 else x


def _fold(ins, defs):
    """The constant value of `ins`'s single result, or None."""
    op = ins.op
    if len(ins.results) != 1:
        return None
    vals = [_const(v, defs) for v in ins.operands]
    if any(x is None for x in vals) or not vals:
        return None
    t = ins.result.type
    try:
        if op in ('add', 'sub', 'mul') and t == I.I64:
            a, b = vals
            r = a + b if op == 'add' else a - b if op == 'sub' else a * b
            return r if -(1 << 63) <= r < (1 << 63) else None
        if op == 'neg' and t == I.I64:
            r = -vals[0]
            return r if -(1 << 63) <= r < (1 << 63) else None
        if op in ('and', 'or', 'xor'):
            a, b = vals
            if t == I.I1:
                a, b = bool(a), bool(b)
                return (a and b) if op == 'and' else (a or b) if op == 'or' else (a != b)
            return a & b if op == 'and' else a | b if op == 'or' else a ^ b
        if op == 'inv':
            return ~vals[0]
        if op == 'zext':
            return int(bool(vals[0]))
        if op.startswith('cmp.'):
            a, b = vals
            return {'eq': a == b, 'ne': a != b, 'lt': a < b, 'le': a <= b, 'gt': a > b,
                    'ge': a >= b}[op[4:]]
        if op == 'select':
            return vals[1] if vals[0] else vals[2]
        if op in ('floordiv', 'floormod') and t == I.I64:
            a, b = vals
            if b == 0 or (op == 'floordiv' and a == -(1 << 63) and b == -1):
                return None
            return a // b if op == 'floordiv' else a % b
        if op == 'shr' and t == I.I64:
            a, b = vals
            return a >> b if 0 <= b < 64 else None
        if op == 'shl' and t == I.I64:
            a, b = vals
            if not 0 <= b < 64:
                return None
            r = a << b
            return r if -(1 << 63) <= r < (1 << 63) else None
    except (TypeError, ValueError, OverflowError):
        return None
    return None


def _identity(ins, defs):
    """x + 0, 0 + x, x - 0, x * 1, 1 * x, x | 0, x ^ 0, x << 0, x >> 0 (ints; never raise): x."""
    op = ins.op
    if op not in ('add', 'sub', 'mul', 'or', 'xor', 'shl', 'shr') or len(ins.operands) != 2:
        return None
    a, b = ins.operands
    if a.type != I.I64 or ins.result.type != I.I64:
        return None
    ca, cb = _const(a, defs), _const(b, defs)
    unit = 1 if op == 'mul' else 0
    if cb == unit and not isinstance(cb, bool):
        return a
    if op in ('add', 'mul', 'or', 'xor') and ca == unit and not isinstance(ca, bool):
        return b
    return None


class Simplifier(object):
    def __init__(self, fn):
        self.fn = fn
        self.changed = False
        self.replace = {}

    def sub(self, v):
        while v in self.replace:
            v = self.replace[v]
        return v

    # ------------------------------------------------------------------ folding + CSE
    def fold_region(self, region, defs, avail):
        out = []
        instrs = list(region.instrs)
        k = 0
        while k < len(instrs):
            ins = instrs[k]
            k += 1
            ins.operands = [self.sub(v) for v in ins.operands]
            if ins.op == 'select':
                c = _const(ins.operands[0], defs)
                if c is not None:
                    self.replace[ins.result] = ins.operands[1] if c else ins.operands[2]
                    self.changed = True
                    continue
                if ins.operands[1] is ins.operands[2]:
                    self.replace[ins.result] = ins.operands[1]
                    self.changed = True
                    continue
            if ins.op == 'if':
                c = _const(ins.operands[0], defs)
                if c is not None:
                    arm = ins.regions[0] if c else ins.regions[1]
                    self.changed = True
                    term = arm.instrs[-1]
                    body = arm.instrs[:-1]
                    if term.op == 'yield':
                        for r, v in zip(ins.results, term.operands):
                            self.replace[r] = v
                        instrs[k:k] = body
                        continue
                    instrs[k:] = body + [term]
                    continue
            same = _identity(ins, defs)
            if same is not None:
                self.replace[ins.result] = same
                self.changed = True
                continue
            if not ins.regions and ins.op != 'const':
                value = _fold(ins, defs)
                if value is not None:
                    t = ins.result.type
                    if t == I.I1:
                        value = bool(value)
                    elif t.is_int:
                        value = int(value)
                    ins.op, ins.operands, ins.attrs = 'const', [], {'value': value}
                    self.changed = True
            if is_pure(ins, defs) and ins.op != 'const' and len(ins.results) == 1:
                key = (ins.op, tuple(id(v) for v in ins.operands), repr(sorted(ins.attrs.items())),
                       ins.result.type)
                if key in avail:
                    self.replace[ins.result] = avail[key]
                    self.changed = True
                    continue
                avail[key] = ins.result
            if ins.op == 'const' and len(ins.results) == 1:
                key = ('const', ins.result.type, repr(ins.attrs.get('value')))
                if key in avail:
                    self.replace[ins.result] = avail[key]
                    self.changed = True
                    continue
                avail[key] = ins.result
            for r in ins.results:
                defs[r] = ins
            for r in ins.regions:
                self.fold_region(r, defs, dict(avail))
            out.append(ins)
        region.instrs = out

    # ------------------------------------------------------------------ dead code
    def uses(self):
        count = {}

        def walk(region):
            for ins in region.instrs:
                for v in ins.operands:
                    count[v] = count.get(v, 0) + 1
                for r in ins.regions:
                    walk(r)
        walk(self.fn.body)
        return count

    def dce_live(self, defs):
        """Liveness of values through control flow: a value is live when an instruction that has to stay (an
        effect, a raise, a store, a condition, a bound, a return) uses it, or when it is a result or carried
        value that feeds a live value. The carried values and `if` results that are not live are removed.
        (The local rule below only sees a carried value that carries itself; this one also removes a chain
        that runs through nested loops, which the C compiler would otherwise keep in registers.)"""
        fn = self.fn
        live = set()
        work = []
        loops = []                 # enclosing loops while walking
        uses_of = {}               # value -> [(kind, ...)] edges: value becomes live => operands become live
        edges = {}                 # value -> values that become live when it does

        def link(v, *deps):
            edges.setdefault(v, []).extend(d for d in deps if d is not None)

        def mark(v):
            if v not in live:
                live.add(v)
                work.append(v)

        def walk(region, loops):
            for ins in region.instrs:
                op = ins.op
                inner = loops
                if op == 'if':
                    mark(ins.operands[0])
                    for j, r in enumerate(ins.results):
                        for arm in ins.regions:
                            y = arm.instrs[-1]
                            if y.op == 'yield' and j < len(y.operands):
                                link(r, y.operands[j])
                elif op in I.LOOP_OPS:
                    body = ins.regions[0]
                    if op == 'for.range':
                        for v in ins.operands[:3]:
                            mark(v)
                        for k, r in enumerate(ins.results):
                            link(r, body.args[1 + k])
                        for k in range(len(body.args) - 1):
                            link(body.args[1 + k], ins.operands[3 + k])
                    else:
                        for k, a in enumerate(body.args):
                            link(a, ins.operands[k])
                    inner = loops + [ins]
                elif op in ('break', 'continue'):
                    loop = loops[-1] if loops else None
                    if loop is not None:
                        body = loop.regions[0]
                        if op == 'continue':
                            args = body.args[1:] if loop.op == 'for.range' else body.args
                            for k, a in enumerate(args):
                                if k < len(ins.operands):
                                    link(a, ins.operands[k])
                        elif loop.op == 'for.range':
                            for k, r in enumerate(loop.results):
                                if k < len(ins.operands):
                                    link(r, ins.operands[k])
                        else:
                            for j, r in enumerate(loop.results):
                                if j < len(ins.operands):
                                    link(r, ins.operands[j])
                elif op == 'yield':
                    pass
                elif ins.regions:
                    for v in ins.operands:
                        mark(v)
                elif removable(ins, defs):
                    for r in ins.results:
                        link(r, *ins.operands)
                else:
                    for v in ins.operands:
                        mark(v)
                for r in ins.regions:
                    walk(r, inner)
        walk(fn.body, [])
        while work:
            v = work.pop()
            for d in edges.get(v, ()):
                mark(d)
        changed = False
        for ins in list(I.walk(fn.body)):
            if ins.op == 'if':
                keep = [j for j, r in enumerate(ins.results) if r in live]
                if len(keep) != len(ins.results):
                    for arm in ins.regions:
                        y = arm.instrs[-1]
                        if y.op == 'yield':
                            y.operands = [y.operands[j] for j in keep]
                    ins.results = [ins.results[j] for j in keep]
                    changed = True
            elif ins.op in I.LOOP_OPS:
                body = ins.regions[0]
                exits = self.loop_exits(ins)
                if ins.op == 'for.range':
                    keepk = [k for k in range(len(body.args) - 1)
                             if body.args[1 + k] in live or ins.results[k] in live]
                    if len(keepk) != len(body.args) - 1:
                        body.args = [body.args[0]] + [body.args[1 + k] for k in keepk]
                        ins.operands = ins.operands[:3] + [ins.operands[3 + k] for k in keepk]
                        for e in exits:
                            e.operands = [e.operands[k] for k in keepk]
                        ins.results = [ins.results[k] for k in keepk]
                        changed = True
                else:
                    keepk = [k for k, a in enumerate(body.args) if a in live]
                    if len(keepk) != len(body.args):
                        body.args = [body.args[k] for k in keepk]
                        ins.operands = [ins.operands[k] for k in keepk]
                        for e in exits:
                            if e.op == 'continue':
                                e.operands = [e.operands[k] for k in keepk]
                        changed = True
                    keepj = [j for j, r in enumerate(ins.results) if r in live]
                    if len(keepj) != len(ins.results):
                        for e in exits:
                            if e.op == 'break':
                                e.operands = [e.operands[j] for j in keepj]
                        ins.results = [ins.results[j] for j in keepj]
                        changed = True

        # instructions nothing live uses (they may still name a carried value that was just removed)
        def prune(region):
            nonlocal changed
            out = []
            for ins in region.instrs:
                for r in ins.regions:
                    prune(r)
                if ins.results and not ins.regions and removable(ins, defs) \
                        and all(r not in live for r in ins.results):
                    changed = True
                    continue
                out.append(ins)
            region.instrs = out
        prune(fn.body)
        return changed

    def dce(self, defs):
        changed = self.dce_live(defs)
        count = self.uses()
        # carried values and results
        for ins in list(I.walk(self.fn.body)):
            if ins.op == 'if':
                keep = [j for j, r in enumerate(ins.results) if count.get(r, 0)]
                if len(keep) != len(ins.results):
                    for arm in ins.regions:
                        y = arm.instrs[-1]
                        if y.op == 'yield':
                            y.operands = [y.operands[j] for j in keep]
                    ins.results = [ins.results[j] for j in keep]
                    changed = True
            elif ins.op in I.LOOP_OPS:
                changed |= self.dce_loop(ins, count)
        if changed:
            count = self.uses()

        def walk(region):
            nonlocal changed
            out = []
            for ins in region.instrs:
                for r in ins.regions:
                    walk(r)
                if removable(ins, defs) and all(not count.get(r, 0) for r in ins.results):
                    for v in ins.operands:
                        count[v] -= 1
                    changed = True
                    continue
                out.append(ins)
            region.instrs = out
        walk(self.fn.body)
        return changed

    def loop_exits(self, loop):
        """break/continue instructions that belong to `loop` (not to a nested loop)."""
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

    def dce_loop(self, loop, count):
        body = loop.regions[0]
        skip = 1 if loop.op == 'for.range' else 0
        first = 3 if loop.op == 'for.range' else 0
        exits = self.loop_exits(loop)
        changed = False
        k = 0
        while k < len(body.args) - skip:
            a = body.args[skip + k]
            own = sum(1 for e in exits if e.op == 'continue' and e.operands[k] is a)
            if loop.op == 'for.range':
                if count.get(loop.results[k], 0):
                    k += 1
                    continue
                own += sum(1 for e in exits if e.op == 'break' and e.operands[k] is a)
            if count.get(a, 0) != own:
                k += 1
                continue
            del body.args[skip + k]
            del loop.operands[first + k]
            for e in exits:
                if e.op == 'continue' or loop.op == 'for.range':
                    del e.operands[k]
            if loop.op == 'for.range':
                del loop.results[k]
            changed = True
            count = self.uses()
        if loop.op == 'loop':
            keep = [j for j, r in enumerate(loop.results) if count.get(r, 0)]
            if len(keep) != len(loop.results):
                for e in exits:
                    if e.op == 'break':
                        e.operands = [e.operands[j] for j in keep]
                loop.results = [loop.results[j] for j in keep]
                changed = True
        return changed


def apply_replace(fn, replace):
    def sub(v):
        while v in replace:
            v = replace[v]
        return v
    for ins in I.walk(fn.body):
        ins.operands = [sub(v) for v in ins.operands]


def run(fn, rounds=8):
    """Fold, CSE and DCE `fn` to a fixed point (bounded); returns whether anything changed."""
    any_change = False
    for _ in range(rounds):
        s = Simplifier(fn)
        defs = {}
        s.fold_region(fn.body, defs, {})
        apply_replace(fn, s.replace)
        defs = {r: ins for ins in I.walk(fn.body) for r in ins.results}
        changed = s.dce(defs) or s.changed
        any_change |= changed
        if not changed:
            break
    return any_change
