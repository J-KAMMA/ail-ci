"""Tagged ints that provably fit int64 become plain i64 (the "tint demotion").

The Python surface keeps an `int` that is not proven small as a `tint` (an `ail_tint`: a small value or a
bignum). Every operation on one costs a call and a tag test, an index made from one goes through
`ail_tint_i64` and, because it is a tint, the range pass sees nothing about it: no bounds check through
it is ever proven. This pass runs the range analysis (ranges.py) over the tagged values too, with facts
over the mathematical integers (nothing clipped), and rewrites the ones whose fact lies inside
[-2^63, 2^63 - 1]:

* S, the set of demoted values, is a fixed point: a value is in S only if its fact is within int64 AND
  every tagged value it is computed from is in S. The producers that can be in S are `tint.from`,
  `tint.add/sub/mul` (and the `_i64` forms), `tint.neg`, `select`, the block arguments and results of
  loops and `if`s, and the index of a tagged `for.range`. Anything else (a parameter, a call, a load, a
  shift, `//`, `%`, ...) is unknown, so nothing that depends on it is in S. A loop's carried argument
  and its result are in S together, so are all the values they are computed from, so the carried value
  is the same type on every edge.
* Why this is exact: a value in S is, on every execution that reaches it, a mathematical integer in int64,
  so `ail_tint_*` on it returns the same integer as the plain operation, and the plain operation
  (`nsw`: the analysis proved the exact result fits) cannot overflow. The facts are the ones ranges.py
  computes for i64: the interval arithmetic is exact, loops are iterated to a fixed point (widening to
  +-BIG), the guard of a `while` refines the loop variable, and only the final visit counts.
* Consumers: `tint.i64 x` is x (it cannot raise on a value in int64), a tagged comparison becomes `cmp`,
  `tint.f64` `sitofp`, `tint.nonzero` `cmp.ne x, 0`. Every other consumer (a call, a store, a shift, a
  `return`, a tagged operation with a value outside S) gets `tint.from x`: the same tagged value it had.
* One more rewrite needs no range: a tagged `+ - *` or `neg` whose operands are in S and whose result
  is used only by `tint.i64` is the checked i64 operation (`ck`): when the exact result does not fit,
  `tint.i64` stops with "integer overflow" and so does `ck_add`, at the same point, with the same text,
  and nothing else could observe the bignum in between.
"""
import os

from .. import ir as I
from . import ranges as R

MIN, MAX = R.MIN, R.MAX

_ARITH = {'tint.add': 'add', 'tint.sub': 'sub', 'tint.mul': 'mul',
          'tint.add_i64': 'add', 'tint.sub_i64': 'sub', 'tint.mul_i64': 'mul', 'tint.neg': 'neg'}
# by a constant divisor (ranges.tint_eval gives a fact only then): the i64 operation is Python's, and cannot raise
_DIVMOD = {'tint.floordiv_i64': 'floordiv', 'tint.mod_i64': 'floormod', 'tint.mod_pos_i64': 'floormod'}
_CMP = {'tint.eq': 'eq', 'tint.ne': 'ne', 'tint.lt': 'lt', 'tint.le': 'le',
        'tint.eq_i64': 'eq', 'tint.ne_i64': 'ne', 'tint.lt_i64': 'lt', 'tint.le_i64': 'le'}


class _Loop(object):
    def __init__(self, ins):
        self.ins = ins
        self.continues = []
        self.breaks = []


def _has_tint(fn):
    for p in fn.params:
        if p.type == I.TINT:
            return True
    for ins in I.walk(fn.body):
        if ins.op.startswith('tint.'):
            return True
    return False


def run(fn, facts=None):
    if not _has_tint(fn):
        return {}
    an = R.Analysis(fn, facts)
    env = {}
    params = (facts or {}).get('params') or {}
    for p, n in zip(fn.params, fn.param_names):
        if n in params and p.type == I.I64:
            lo, hi = params[n]
            env[p] = R.Fact(lo, hi)
    an.region(fn.body, env, [])

    feeders = {}        # tagged value -> the tagged values it is computed from (it can be in S)
    pair = {}           # loop carried argument <-> result
    loops = {}
    uses = {}

    def visit(region, stack):
        for ins in region.instrs:
            op = ins.op
            for v in ins.operands:
                uses.setdefault(v, []).append(ins)
            if op == 'if':
                for j, r in enumerate(ins.results):
                    if r.type == I.TINT:
                        fs = []
                        for arm in ins.regions:
                            t = arm.instrs[-1] if arm.instrs else None
                            if t is not None and t.op == 'yield':
                                fs.append(t.operands[j])
                        feeders[r] = fs
                for arm in ins.regions:
                    visit(arm, stack)
            elif op in I.LOOP_OPS:
                body = ins.regions[0]
                rec = _Loop(ins)
                loops[ins] = rec
                visit(body, stack + [rec])
                if op == 'for.range':
                    args, init = body.args[1:], ins.operands[3:]
                    if body.args[0].type == I.TINT:
                        feeders[body.args[0]] = [v for v in ins.operands[:3] if v.type == I.TINT]
                else:
                    args, init = body.args, ins.operands
                for j, a in enumerate(args):
                    if a.type == I.TINT:
                        feeders[a] = [init[j]] + [c.operands[j] for c in rec.continues]
                for j, r in enumerate(ins.results):
                    if r.type == I.TINT:
                        fs = [b.operands[j] for b in rec.breaks]
                        if op == 'for.range':
                            fs.append(args[j])
                        feeders[r] = fs
                        pair[r] = args[j]
                        pair[args[j]] = r
            elif op == 'continue':
                stack[-1].continues.append(ins)
            elif op == 'break':
                stack[-1].breaks.append(ins)
            elif ins.results and ins.results[0].type == I.TINT:
                r = ins.results[0]
                if op == 'tint.from':
                    feeders[r] = []
                elif op in _ARITH or op in _DIVMOD:
                    feeders[r] = [v for v in ins.operands if v.type == I.TINT]
                elif op == 'select':
                    feeders[r] = list(ins.operands[1:])

    visit(fn.body, [])

    def small(v):
        f = an.vfacts.get(v)
        return f is not None and MIN <= f.lo and f.hi <= MAX

    S = set(v for v in feeders if small(v))
    if os.environ.get('AIL_TINT_DEBUG'):
        out = open(os.environ['AIL_TINT_DEBUG'], 'a')
        for v in feeders:
            out.write('tintnarrow %s: %s %s fact=%r feeders=%s\n' % (
                fn.name, v, 'S' if v in S else '-', an.vfacts.get(v), [an.vfacts.get(w) for w in feeders[v]]))
    changed = True
    while changed:
        changed = False
        for v in list(S):
            if any(w.type == I.TINT and w not in S for w in feeders[v]) or (v in pair and pair[v] not in S):
                S.discard(v)
                changed = True

    # ---- the checked fusion: a tagged + - * neg of values in S that only `tint.i64` reads
    fuse = set()
    for ins in I.walk(fn.body):
        if ins.op in _ARITH and ins.results[0].type == I.TINT and ins.results[0] not in S:
            r = ins.results[0]
            if all(v in S for v in ins.operands if v.type == I.TINT) \
                    and uses.get(r) and all(u.op == 'tint.i64' for u in uses[r]):
                fuse.add(ins)
    if not S and not fuse:
        return {}

    otype = {ins: [v.type for v in ins.operands] for ins in I.walk(fn.body)}     # before the retyping
    for v in S:
        v.type = I.I64
    alias = {}

    def res(v):
        while v in alias:
            v = alias[v]
        return v

    counts = {'tint_demoted': len(S), 'tint_fused': len(fuse)}

    def rewrite(region, ytargets, lctx):
        """`ytargets`: the results a `yield` of this region feeds (an `if` arm), `lctx`: the (arguments, results)
        a `continue` and a `break` feed (the innermost loop around this region)."""
        out = []
        for ins in region.instrs:
            ins.operands = [res(v) for v in ins.operands]
            op = ins.op
            # operands in S are plain i64 now; a consumer that still wants a tint gets `tint.from`
            def wrap(k):
                t = I.Value(I.TINT)
                out.append(I.Instr('tint.from', [ins.operands[k]], [t]))
                ins.operands[k] = t

            if op == 'tint.from' and ins.results[0] in S:
                alias[ins.results[0]] = ins.operands[0]
                continue
            if op in _ARITH and ins.results[0] in S:
                ins.attrs = {'mode': 'nsw'}
                ins.op = _ARITH[op]
                out.append(ins)
                continue
            if op in _DIVMOD and ins.results[0] in S:
                ins.attrs = {'mode': 'ck'}
                ins.op = _DIVMOD[op]
                out.append(ins)
                continue
            if op in _ARITH and ins in fuse:
                ins.attrs = {'mode': 'ck'}
                ins.op = _ARITH[op]
                ins.results[0].type = I.I64
                out.append(ins)
                for u in uses[ins.results[0]]:
                    alias[u.results[0]] = ins.results[0]
                continue
            if op == 'tint.i64' and ins.operands[0].type == I.I64:
                alias[ins.results[0]] = ins.operands[0]
                continue
            if op in _CMP and ins.operands[0].type == I.I64 and (ins.operands[1].type == I.I64):
                ins.op = 'cmp.' + _CMP[op]
                ins.attrs = {}
                out.append(ins)
                continue
            if op == 'tint.f64' and ins.operands[0].type == I.I64:
                ins.op = 'sitofp'
                out.append(ins)
                continue
            if op == 'tint.nonzero' and ins.operands[0].type == I.I64:
                z = I.Instr('const', [], [I.Value(I.I64)], {'value': 0})
                out.append(z)
                ins.op = 'cmp.ne'
                ins.operands = [ins.operands[0], z.result]
                out.append(ins)
                continue
            if op == 'select' and ins.results[0] in S:
                out.append(ins)
                continue
            if op == 'if':
                for arm in ins.regions:
                    arm.instrs = rewrite(arm, ins.results, lctx)
                out.append(ins)
                continue
            if op in I.LOOP_OPS:
                body = ins.regions[0]
                if op == 'for.range':
                    args, first = body.args[1:], 3
                    if body.args[0].type == I.TINT:
                        for k in range(3):
                            if ins.operands[k].type == I.I64:
                                wrap(k)
                else:
                    args, first = body.args, 0
                for j, a in enumerate(args):
                    k = first + j
                    if a.type == I.TINT and ins.operands[k].type == I.I64:
                        wrap(k)
                body.instrs = rewrite(body, (), (args, ins.results))
                out.append(ins)
                continue
            if op in ('yield', 'break', 'continue'):
                if op == 'yield':
                    targets = ytargets
                elif lctx is None:
                    targets = ()
                else:
                    targets = lctx[0] if op == 'continue' else lctx[1]
                for k in range(len(ins.operands)):
                    if k < len(targets) and targets[k].type == I.TINT and ins.operands[k].type == I.I64:
                        wrap(k)
                out.append(ins)
                continue
            # any other consumer: a tint slot gets a tint
            for k, v in enumerate(ins.operands):
                if v.type == I.I64 and otype[ins][k] == I.TINT:
                    wrap(k)
            out.append(ins)
        return out

    fn.body.instrs = rewrite(fn.body, (), None)
    for ins in I.walk(fn.body):
        ins.operands = [res(v) for v in ins.operands]
    return counts

