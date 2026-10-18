"""Speculative selects: a cheap, effect-free `if` on loaded data becomes straight-line code and selects
(docs/design/IR_OWNERSHIP_DESIGN_v2.md section 22).

    %r.. = if %c { A; yield %a.. } { B; yield %b.. }   ->   A'; B'; %r.. = select(%c, %a.., %b..)

A branch whose test reads a container element mispredicts on irregular data (a grid-life program's cell update:
`if s == 1 { if rule[wt] == 1 {..} else {..} } elif s == 0 {..}`, about a third of the time on a random
grid). Running both arms and selecting the results costs a few instructions and no misprediction.
Ifs are flattened innermost first, so a nest whose every arm qualifies becomes one block.

An arm qualifies when every instruction in it (none of them holding a region) is one of:
  * pure arithmetic: const, cmp, zext, select, and/or/xor/inv, fadd/fsub/fmul, sitofp, and add/sub/mul/neg
    in mode nsw or wrap -- hoisted as wrap, because a range proof may hold only on the arm's own path
    (the value is used only where it does, and a wrapped add is the same machine add);
  * a read that cannot fault: `load` of a place that an earlier instruction of the function body (outside
    any region) has stored or initialised -- never the zero a place starts as -- and `field.list` /
    scalar `field.get` of an object;
  * an element read `list.get` / `span.get` of an int or float list (checked or proven): it becomes
    `spec.get %list, %i, %guard`, which reads the element when the index is in range, fails exactly as the
    original would when the guard (the arm's condition, and-ed with any guard it already had) holds, and
    otherwise yields 0 without touching memory. So an IndexError happens exactly when it did;
  * a checked `add`/`sub` (x, d) whose only use is the arm's yield at position j, where the other arm
    yields x or the same op on x: the result becomes `x op select(%c, d, 0)` (or `select(%c, d, d')`).
    Adding 0 never overflows, so OverflowError happens exactly when it did (the ifadd rule, generalised).
    Such an add may not precede an element read in its arm (the read's IndexError would come first now),
    and an arm's adds must be in yield order (two failures keep their order).

Nothing is stored, called, allocated or resized in either arm, so no alias relation and no memory state
changes. An if whose results are all i1 (the lowering of `and`/`or`) is left alone: its value feeds a
branch anyway; so is one whose test compares with a loop-carried value (a running max or min: taken ever
more rarely, so predictable; a tree parser ran +1.6% cycles converted). The if must sit in a loop, its test must read a container element within a few pure steps (a
test of locals is predictable: k_nucleotide ran 3% slower when such a branch was converted), and the two
arms together may hoist at most LIMIT instructions.
"""
from .. import ir as I

LIMIT = 24
_PURE = {'const', 'zext', 'select', 'and', 'or', 'xor', 'inv', 'fadd', 'fsub', 'fmul', 'sitofp',
         'cmp.eq', 'cmp.ne', 'cmp.lt', 'cmp.le', 'cmp.gt', 'cmp.ge'}
_WRAPPABLE = {'add', 'sub', 'mul', 'neg'}
_ELEMENT = ('list.get', 'span.get', 'spec.get')
_READS = _ELEMENT + ('ba.get', 'bytes.get', 'field.get')
_NUM = (I.I64, I.F64)
_INITS = ('store', 'obj.init', 'obj.copyref', 'ba.new', 'ba.call')


class _Abort(Exception):
    pass


def _elem_ok(container):
    t = container.type
    if t.head == 'obj' and t.args[0].head == 'list':
        return t.args[0].args[0] in _NUM
    if t.head == 'span':
        return t.args[0] in _NUM
    return False


class _Arm(object):
    __slots__ = ('hoist', 'defer', 'cost', 'yields', 'local')

    def __init__(self):
        self.hoist = []      # instructions to run unconditionally, in order
        self.defer = {}      # result of a checked add/sub -> (op, operands)
        self.cost = 0
        self.yields = []
        self.local = set()   # values defined in the arm


class _Pass(object):
    def __init__(self, fn):
        self.fn = fn
        self.defs = {}
        self.uses = {}
        self.replace = {}
        self.carried = set()     # loop-carried values (block arguments of loop bodies)
        for ins in I.walk(fn.body):
            for r in ins.results:
                self.defs[r] = ins
            for v in ins.operands:
                self.uses[v] = self.uses.get(v, 0) + 1
            if ins.op in I.LOOP_OPS:
                self.carried.update(ins.regions[0].args)
        # places written by an instruction of the function body itself: valid after that instruction
        self.ready = {}
        for k, ins in enumerate(fn.body.instrs):
            if ins.op in _INITS and ins.operands:
                self.ready.setdefault(ins.operands[0], k)
        self.count = 0

    def sub(self, v):
        while v in self.replace:
            v = self.replace[v]
        return v

    def rename(self, old, new):
        self.replace[old] = new
        self.uses[new] = self.uses.get(new, 0) + self.uses.get(old, 0)

    def new(self, out, op, operands, type_, attrs=None):
        v = I.Value(type_)
        ins = I.Instr(op, operands, [v], attrs or {})
        out.append(ins)
        self.defs[v] = ins
        for o in operands:
            self.uses[o] = self.uses.get(o, 0) + 1
        return v

    def reads_element(self, v, depth=4):
        d = self.defs.get(v)
        if d is None or depth == 0:
            return False
        if d.op in _READS:
            return True
        if d.op in _PURE or d.op in _WRAPPABLE:
            return any(self.reads_element(o, depth - 1) for o in d.operands)
        return False

    # ---------------------------------------------------------------- the walk
    def region(self, region, top_index, in_loop):
        for k, ins in enumerate(region.instrs):
            index = k if top_index is None else top_index
            for r in ins.regions:
                self.region(r, index, in_loop or ins.op in I.LOOP_OPS)
        if not in_loop:
            return
        out = []
        changed = False
        for k, ins in enumerate(region.instrs):
            index = k if top_index is None else top_index
            if ins.op == 'if' and ins.results:
                flat = self.flatten(ins, index)
                if flat is not None:
                    out.extend(flat)
                    changed = True
                    continue
            out.append(ins)
        if changed:
            region.instrs = out

    def plan(self, region, index):
        instrs = region.instrs
        if not instrs or instrs[-1].op != 'yield':
            raise _Abort()
        for ins in instrs:
            ins.operands = [self.sub(v) for v in ins.operands]
        arm = _Arm()
        arm.yields = list(instrs[-1].operands)
        for ins in instrs[:-1]:
            if ins.regions or len(ins.results) != 1:
                raise _Abort()
            op = ins.op
            if op in ('add', 'sub') and ins.attrs.get('mode') == 'ck':
                r = ins.result
                if (self.uses.get(r, 0) != 1 or arm.yields.count(r) != 1 or ins.result.type != I.I64
                        or any(o in arm.defer for o in ins.operands)):
                    raise _Abort()
                arm.defer[r] = (op, list(ins.operands))
                arm.local.add(r)
                continue
            if op in _ELEMENT:
                if arm.defer or not _elem_ok(ins.operands[0]):
                    raise _Abort()          # an IndexError would now come before an earlier OverflowError
            elif op == 'load':
                k = self.ready.get(ins.operands[0])
                if k is None or k >= index:
                    raise _Abort()
            elif op in ('field.list', 'field.get'):
                t = ins.operands[0].type
                if t.head != 'obj' or t.args[0].head != 'class':
                    raise _Abort()
                if op == 'field.get' and ins.result.type not in (I.I64, I.F64, I.I1):
                    raise _Abort()
            elif op in _WRAPPABLE:
                if ins.attrs.get('mode') not in ('nsw', 'wrap'):
                    raise _Abort()
            elif op not in _PURE:
                raise _Abort()
            if any(o in arm.defer for o in ins.operands):
                raise _Abort()              # a deferred add's result feeds something else
            if op != 'const':
                arm.cost += 1
            arm.hoist.append(ins)
            arm.local.add(ins.result)
        order = [arm.yields.index(r) for r in arm.defer]
        if order != sorted(order):
            raise _Abort()
        return arm

    def merge(self, t, e):
        """Per result: ('same', v) | ('select', a, b) | ('add', op, x, da, db)."""
        out = []
        outside = lambda x: x not in t.local and x not in e.local
        for a, b in zip(t.yields, e.yields):
            if a not in t.defer and b not in e.defer:
                out.append(('same', a) if a is b else ('select', a, b))
                continue
            if a in t.defer and b in e.defer:
                op_a, (a0, a1) = t.defer[a]
                op_b, (b0, b1) = e.defer[b]
                if op_a != op_b:
                    raise _Abort()
                pairs = [(a0, a1, b0, b1)]
                if op_a == 'add':
                    pairs += [(a1, a0, b0, b1), (a0, a1, b1, b0), (a1, a0, b1, b0)]
                for xa, da, xb, db in pairs:
                    if xa is xb and outside(xa):
                        out.append(('add', op_a, xa, da, db))
                        break
                else:
                    raise _Abort()
                continue
            then_side = a in t.defer
            op, (o0, o1) = t.defer[a] if then_side else e.defer[b]
            plain = b if then_side else a
            cands = [(o0, o1)] + ([(o1, o0)] if op == 'add' else [])
            for x, d in cands:
                if x is plain and outside(x):
                    out.append(('add', op, x, d, None) if then_side else ('add', op, x, None, d))
                    break
            else:
                raise _Abort()
        return out

    def flatten(self, ins, index):
        c = self.sub(ins.operands[0])
        if all(r.type == I.I1 for r in ins.results):
            return None     # an `and`/`or` test: it feeds a branch anyway (as in ifadd), left alone
        if not self.reads_element(c):
            return None
        d = self.defs.get(c)
        if d is not None and d.op.startswith('cmp.') and any(o in self.carried for o in d.operands):
            return None     # a running max/min (`if xs[i] > m: m = xs[i]`): taken ever more rarely, predictable
        try:
            t = self.plan(ins.regions[0], index)
            e = self.plan(ins.regions[1], index)
            if len(t.yields) != len(ins.results) or len(e.yields) != len(ins.results):
                raise _Abort()
            if t.cost + e.cost > LIMIT:
                raise _Abort()
            merged = self.merge(t, e)
        except _Abort:
            return None
        out = []
        not_c = []

        def guard(then_arm, g):
            if then_arm:
                base = c
            else:
                if not not_c:
                    true = self.new(out, 'const', [], I.I1, {'value': True})
                    not_c.append(self.new(out, 'xor', [c, true], I.I1))
                base = not_c[0]
            return base if g is None else self.new(out, 'and', [base, g], I.I1)

        for then_arm, arm in ((True, t), (False, e)):
            for h in arm.hoist:
                if h.op in ('list.get', 'span.get'):
                    g = guard(then_arm, None)
                    self.rename(h.result, self.new(out, 'spec.get', [h.operands[0], h.operands[1], g], h.result.type))
                    continue
                if h.op == 'spec.get':
                    h.operands[2] = guard(then_arm, h.operands[2])
                elif h.op in _WRAPPABLE and h.attrs.get('mode') == 'nsw':
                    h.attrs['mode'] = 'wrap'
                out.append(h)
        zero = []
        for r, m in zip(ins.results, merged):
            if m[0] == 'same':
                self.rename(r, m[1])
            elif m[0] == 'select':
                self.rename(r, self.new(out, 'select', [c, self.sub(m[1]), self.sub(m[2])], r.type, {'spec': True}))
            else:
                _k, op, x, da, db = m
                if da is None or db is None:
                    if not zero:
                        zero.append(self.new(out, 'const', [], I.I64, {'value': 0}))
                    da = zero[0] if da is None else da
                    db = zero[0] if db is None else db
                d = self.new(out, 'select', [c, self.sub(da), self.sub(db)], I.I64, {'spec': True})
                self.rename(r, self.new(out, op, [x, d], I.I64, {'mode': 'ck'}))
        self.count += 1
        return out


def run(fn):
    """Flatten the qualifying ifs of `fn` in place; returns how many were flattened."""
    p = _Pass(fn)
    p.region(fn.body, None, False)
    if p.count:
        for ins in I.walk(fn.body):
            ins.operands = [p.sub(v) for v in ins.operands]
    return p.count
