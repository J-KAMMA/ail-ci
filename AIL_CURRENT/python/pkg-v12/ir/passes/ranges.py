"""Value-range analysis on SSA (design §3.2): proves int64 overflow checks (and, with containers,
index checks) cannot fire, and drops them.

Domain, per i64 value: an interval [lo, hi] (Python ints) plus symbolic bounds `ub = {w: c}`
(v <= w + c) and `lb = {w: c}` (v >= w + c) against other SSA values. The analysis is an abstract
interpreter over the structured regions:

* constants are exact; parameters come from `facts['params']` (whole-program call-site ranges)
  or are unknown; calls' results from `facts['results']` or unknown;
* `if` arms are analysed under the refinement of their condition (cmp, `not`, and the `if`-shaped
  `and`/`or` the lowering produces); when only one arm falls through, the code after the `if`
  keeps that arm's refinements (a guard `if x < 0: return`, or a `while` test);
* a loop is iterated to a fixed point over its carried values (join of the initial value and every
  `continue`), widening bounds that still move after 3 rounds to the int64 limits; a
  `for.range` index with step 1 lies in [lo, hi - 1] and is symbolically < hi and >= lo;
* + - * and unary - are evaluated exactly on the intervals; when the exact result interval fits
  in int64 the checked op becomes `nsw` (the emitter prints the plain C operator); after a checked
  op the result is clipped to int64 (otherwise it raised);
* `//` and `%` by a positive constant of a non-negative value get mode `nonneg` (plain C / and %,
  which equal Python's floor division there);
* a tagged int (`tint`, the exact Python int of the Python surface) has a fact over the mathematical
  integers: nothing is clipped (its operations never raise), an unknown one is [-BIG, BIG], and the
  facts of `tint.from`, `tint.add/sub/mul` (and the `_i64` forms), `tint.neg`, selects, block arguments
  and `if` results follow the same rules as for i64. `Analysis.vfacts` records the final fact of every
  value; tintnarrow.py turns a tint whose fact lies in int64 into a plain i64.

Only the final (stable) visit of each instruction decides its mode, so every decision holds for
every execution that reaches it.
"""
from .. import ir as I

MIN, MAX = -(1 << 63), (1 << 63) - 1
LEN_MAX = 1 << 48
WIDEN_AFTER = 3
NARROW_ROUNDS = 3
BIG = 1 << 200                      # "unbounded" for a tint fact


class Fact(object):
    __slots__ = ('lo', 'hi', 'ub', 'lb')

    def __init__(self, lo=MIN, hi=MAX, ub=None, lb=None):
        self.lo, self.hi = lo, hi
        self.ub = ub or {}
        self.lb = lb or {}

    def __eq__(self, o):
        return (self.lo, self.hi, self.ub, self.lb) == (o.lo, o.hi, o.ub, o.lb)

    def __ne__(self, o):
        return not self == o

    def __repr__(self):
        return 'Fact[%s, %s]' % (self.lo, self.hi)

    @property
    def empty(self):
        return self.lo > self.hi


TOP = Fact()
TOPT = Fact(-BIG, BIG)              # an unknown tint


def join(a, b):
    if a is None:
        return b
    if b is None:
        return a
    ub = {w: max(c, b.ub[w]) for w, c in a.ub.items() if w in b.ub}
    lb = {w: min(c, b.lb[w]) for w, c in a.lb.items() if w in b.lb}
    return Fact(min(a.lo, b.lo), max(a.hi, b.hi), ub, lb)


def widen(old, new, lim=(MIN, MAX)):
    lo = new.lo if new.lo >= old.lo else lim[0]
    hi = new.hi if new.hi <= old.hi else lim[1]
    ub = {w: c for w, c in new.ub.items() if w in old.ub and c <= old.ub[w]}
    lb = {w: c for w, c in new.lb.items() if w in old.lb and c >= old.lb[w]}
    return Fact(lo, hi, ub, lb)


def _clip(lo, hi):
    return max(lo, MIN), min(hi, MAX)


def _negate(pred):
    return {'eq': 'ne', 'ne': 'eq', 'lt': 'ge', 'ge': 'lt', 'le': 'gt', 'gt': 'le'}[pred]


_TINT_CMP = {'tint.eq': 'eq', 'tint.ne': 'ne', 'tint.lt': 'lt', 'tint.le': 'le',
             'tint.eq_i64': 'eq', 'tint.ne_i64': 'ne', 'tint.lt_i64': 'lt', 'tint.le_i64': 'le'}


def _swap(pred):
    return {'eq': 'eq', 'ne': 'ne', 'lt': 'gt', 'gt': 'lt', 'le': 'ge', 'ge': 'le'}[pred]


class _Loop(object):
    def __init__(self, ins):
        self.ins = ins
        self.continues = []
        self.breaks = []


class Analysis(object):
    def __init__(self, fn, facts):
        self.fn = fn
        self.facts = facts or {}
        self.defs = {r: ins for ins in I.walk(fn.body) for r in ins.results}
        self.decision = {}          # instr -> new mode (final visit wins)
        self.cmps = {}              # cmp instr -> True/False/None (final visit wins)
        self.index_facts = {}       # checked index instr -> (lo, hi) of its index (final visit)
        self.vfacts = {}            # i64/tint value -> its Fact at its last visit (the stable one)
        self.lens = {}

    # ------------------------------------------------------------------ facts
    def const(self, v):
        ins = self.defs.get(v)
        if ins is not None and ins.op == 'const':
            return ins.attrs.get('value')
        if ins is not None and ins.op == 'tint.from':
            c = self.const(ins.operands[0])
            return c if isinstance(c, int) and not isinstance(c, bool) else None
        return None

    def get(self, env, v):
        f = env.get(v)
        if f is None:
            c = self.const(v)
            if isinstance(c, bool):
                return Fact(int(c), int(c))
            if isinstance(c, int):
                return Fact(c, c)
            return TOPT if v.type == I.TINT else TOP
        return f

    def top_for(self, v):
        return TOPT if v.type == I.TINT else TOP

    def bounds(self, env, v):
        """[lo, hi] including what the symbolic bounds imply (one step)."""
        f = self.get(env, v)
        lo, hi = f.lo, f.hi
        for w, c in f.ub.items():
            if w is not v:
                hi = min(hi, self.get(env, w).hi + c)
        for w, c in f.lb.items():
            if w is not v:
                lo = max(lo, self.get(env, w).lo + c)
        return lo, hi

    def set(self, env, v, f):
        if v.type in (I.I64, I.I1, I.TINT):
            env[v] = f
            self.vfacts[v] = f

    # ------------------------------------------------------------------ refinement
    def atoms(self, v, truth, depth=0):
        """Comparisons implied by the i1 value `v` being `truth`: [(pred, a, b)]."""
        if depth > 8:
            return []
        ins = self.defs.get(v)
        if ins is None:
            return []
        op = ins.op
        if op.startswith('cmp.'):
            a, b = ins.operands
            if self.const(b) is False and op == 'cmp.eq' and b.type == I.I1:
                return self.atoms(a, not truth, depth + 1)
            if a.type != I.I64 or b.type != I.I64:
                return []
            pred = op[4:]
            return [(pred if truth else _negate(pred), a, b)]
        if op in _TINT_CMP:
            a, b = ins.operands
            pred = _TINT_CMP[op]
            return [(pred if truth else _negate(pred), a, b)]
        if op == 'if' and len(ins.results) == 1 and ins.result.type == I.I1:
            then, other = ins.regions
            ty, oy = then.instrs[-1], other.instrs[-1]
            if ty.op != 'yield' or oy.op != 'yield':
                return []
            c = ins.operands[0]
            tv, ov = ty.operands[0], oy.operands[0]
            if self.const(ov) is False and truth:            # c and x
                return self.atoms(c, True, depth + 1) + self.atoms(tv, True, depth + 1)
            if self.const(tv) is True and not truth:          # c or y
                return self.atoms(c, False, depth + 1) + self.atoms(ov, False, depth + 1)
            if self.const(tv) is False and self.const(ov) is True:
                return self.atoms(c, not truth, depth + 1)
        return []

    def refine(self, env, cond, truth):
        for pred, a, b in self.atoms(cond, truth):
            self.refine_cmp(env, pred, a, b)
            self.refine_cmp(env, _swap(pred), b, a)

    def refine_cmp(self, env, pred, a, b):
        """Refine `a` from `a pred b`."""
        if self.const(a) is not None:
            return
        fa = self.get(env, a)
        blo, bhi = self.bounds(env, b)
        lo, hi = fa.lo, fa.hi
        ub, lb = dict(fa.ub), dict(fa.lb)
        bc = self.const(b)
        if pred == 'lt':
            hi = min(hi, bhi - 1)
            if bc is None:
                ub[b] = min(ub.get(b, 0), -1) if b in ub else -1
        elif pred == 'le':
            hi = min(hi, bhi)
            if bc is None:
                ub[b] = min(ub[b], 0) if b in ub else 0
        elif pred == 'gt':
            lo = max(lo, blo + 1)
            if bc is None:
                lb[b] = max(lb[b], 1) if b in lb else 1
        elif pred == 'ge':
            lo = max(lo, blo)
            if bc is None:
                lb[b] = max(lb[b], 0) if b in lb else 0
        elif pred == 'eq':
            lo, hi = max(lo, blo), min(hi, bhi)
            if bc is None:
                ub[b] = min(ub[b], 0) if b in ub else 0
                lb[b] = max(lb[b], 0) if b in lb else 0
        elif pred == 'ne':
            if isinstance(bc, int) and not isinstance(bc, bool):
                if lo == bc:
                    lo += 1
                if hi == bc:
                    hi -= 1
        env[a] = Fact(lo, hi, ub, lb)

    # ------------------------------------------------------------------ evaluation
    def arith(self, ins, env):
        op = ins.op
        a = ins.operands[0]
        alo, ahi = self.bounds(env, a)
        mode = ins.attrs.get('mode')
        if op == 'neg':
            lo, hi = -ahi, -alo
            ok = lo >= MIN and hi <= MAX
            self.decide(ins, ok)
            return Fact(*_clip(lo, hi))
        b = ins.operands[1]
        blo, bhi = self.bounds(env, b)
        if op == 'add':
            lo, hi = alo + blo, ahi + bhi
        elif op == 'sub':
            lo, hi = alo - bhi, ahi - blo
            fa = self.get(env, a)
            if b in fa.lb:                 # a >= b + c  =>  a - b >= c
                lo = max(lo, fa.lb[b])
            if b in fa.ub:
                hi = min(hi, fa.ub[b])
            fb = self.get(env, b)
            for w, c in fa.lb.items():     # a >= w + c and b <= w + d  =>  a - b >= c - d
                if w in fb.ub and w is not a and w is not b:
                    lo = max(lo, c - fb.ub[w])
            for w, c in fa.ub.items():     # a <= w + c and b >= w + d  =>  a - b <= c - d
                if w in fb.lb and w is not a and w is not b:
                    hi = min(hi, c - fb.lb[w])
        else:
            ps = (alo * blo, alo * bhi, ahi * blo, ahi * bhi)
            lo, hi = min(ps), max(ps)
        ok = lo >= MIN and hi <= MAX
        self.decide(ins, ok)
        f = Fact(*_clip(lo, hi))
        bc = self.const(b)
        if op in ('add', 'sub') and isinstance(bc, int) and not isinstance(bc, bool):
            k = bc if op == 'add' else -bc
            fa = self.get(env, a)
            if self.const(a) is None:
                f.ub = {w: c + k for w, c in fa.ub.items()}
                f.lb = {w: c + k for w, c in fa.lb.items()}
                f.ub[a] = k
                f.lb[a] = k
        if mode == 'wrap' and not ok:
            return TOP          # wrapping arithmetic
        return f

    def tint_eval(self, ins, env):
        """The fact of a tagged-int result, over the mathematical integers (no clipping: a tint operation
        never raises). Only the operations tintnarrow.py can turn into plain i64 arithmetic get a fact; any
        other result stays unknown (+-BIG)."""
        op = ins.op
        r = ins.results[0]
        o = ins.operands
        if op == 'tint.from':
            f = self.get(env, o[0])
            if self.const(o[0]) is None:
                env[r] = Fact(f.lo, f.hi, {w: c for w, c in f.ub.items()}, {w: c for w, c in f.lb.items()})
                env[r].ub[o[0]] = 0
                env[r].lb[o[0]] = 0
            else:
                env[r] = Fact(f.lo, f.hi)
            return
        if op == 'tint.neg':
            lo, hi = self.bounds(env, o[0])
            env[r] = Fact(-hi, -lo)
            return
        if op in ('tint.add', 'tint.sub', 'tint.mul', 'tint.add_i64', 'tint.sub_i64', 'tint.mul_i64'):
            k = op[5:].split('_')[0]
            a, b = o
            alo, ahi = self.bounds(env, a)
            blo, bhi = self.bounds(env, b)
            if k == 'add':
                lo, hi = alo + blo, ahi + bhi
            elif k == 'sub':
                lo, hi = alo - bhi, ahi - blo
            else:
                ps = (alo * blo, alo * bhi, ahi * blo, ahi * bhi)
                lo, hi = min(ps), max(ps)
            f = Fact(max(lo, -BIG), min(hi, BIG))
            bc = self.const(b)
            if k in ('add', 'sub') and isinstance(bc, int) and not isinstance(bc, bool) and self.const(a) is None:
                kk = bc if k == 'add' else -bc
                fa = self.get(env, a)
                f.ub = {w: c + kk for w, c in fa.ub.items()}
                f.lb = {w: c + kk for w, c in fa.lb.items()}
                f.ub[a] = kk
                f.lb[a] = kk
            env[r] = f
            return
        if op in ('tint.floordiv_i64', 'tint.mod_i64', 'tint.mod_pos_i64'):
            # by a constant other than 0 and -1: no ZeroDivisionError and no INT64_MIN // -1 (a divisor that is
            # not a constant keeps no fact, so tintnarrow.py leaves the operation tagged)
            c = self.const(o[1])
            if not isinstance(c, int) or isinstance(c, bool) or c in (0, -1):
                return
            alo, ahi = self.bounds(env, o[0])
            if op == 'tint.floordiv_i64':
                lo, hi = (alo // c, ahi // c) if c > 0 else (ahi // c, alo // c)
            elif op == 'tint.mod_i64':
                if c > 0:
                    lo, hi = (alo, ahi) if 0 <= alo and ahi < c else (0, c - 1)
                else:
                    lo, hi = (alo, ahi) if c < alo and ahi <= 0 else (c + 1, 0)
            else:
                # `mod_pos` is C's `%` on a non-negative small value: Python's `%` only where the dividend is >= 0
                if c < 0 or alo < 0:
                    return
                lo, hi = (alo, ahi) if ahi < c else (0, c - 1)
            env[r] = Fact(lo, hi)
            return
        if op == 'select':
            env[r] = join(self.get(env, o[1]), self.get(env, o[2]))

    def lengths_of(self, base):
        """Every `bytes.len` value of `base` (all equal: bytes are immutable)."""
        out = self.lens.get(base)
        if out is None:
            out = [r for r, d in self.defs.items() if d.op in ('bytes.len', 'span.len') and d.operands[0] is base]
            self.lens[base] = out
        return out

    def in_bounds(self, env, base, index, ins=None):
        lo, hi = self.bounds(env, index)
        if ins is not None:
            self.index_facts[ins] = (lo, hi)
        if lo < 0:
            return False
        lens = self.lengths_of(base)
        f = self.get(env, index)
        for w, c in f.ub.items():
            if c <= -1 and w in lens:
                return True
            # index <= w + c and w <= len + d  (one more step through w's own bounds)
            if w in env:
                for w2, c2 in env[w].ub.items():
                    if w2 in lens and c + c2 <= -1:
                        return True
        for L in lens:
            if L in env and env[L].lo > hi:
                return True
        return False

    def decide(self, ins, ok):
        if ins.attrs.get('mode') == 'ck' or ins in self.decision:
            self.decision[ins] = 'nsw' if ok else 'ck'

    def le(self, env, a, b, k):
        """Whether a <= b + k is proven (intervals, symbolic bounds, one step through a third
        value)."""
        alo, ahi = self.bounds(env, a)
        blo, bhi = self.bounds(env, b)
        if ahi <= blo + k:
            return True
        fa, fb = self.get(env, a), self.get(env, b)
        if b in fa.ub and fa.ub[b] <= k:
            return True
        if a in fb.lb and fb.lb[a] >= -k:
            return True
        for w, c in fa.ub.items():
            fw = self.get(env, w)
            if b in fw.ub and c + fw.ub[b] <= k:
                return True
            if w in fb.lb and c - fb.lb[w] <= k:
                return True
        return False

    def decide_cmp(self, ins, env):
        a, b = ins.operands
        if a.type != I.I64 or b.type != I.I64:
            return
        pred = ins.op[4:]
        truth = None
        if pred == 'lt':
            truth = True if self.le(env, a, b, -1) else False if self.le(env, b, a, 0) else None
        elif pred == 'le':
            truth = True if self.le(env, a, b, 0) else False if self.le(env, b, a, -1) else None
        elif pred == 'gt':
            truth = True if self.le(env, b, a, -1) else False if self.le(env, a, b, 0) else None
        elif pred == 'ge':
            truth = True if self.le(env, b, a, 0) else False if self.le(env, a, b, -1) else None
        elif pred in ('eq', 'ne'):
            if self.le(env, a, b, -1) or self.le(env, b, a, -1):
                truth = pred == 'ne'
            elif self.le(env, a, b, 0) and self.le(env, b, a, 0):
                truth = pred == 'eq'
        self.cmps[ins] = truth          # the final (stable) visit decides

    def evaluate(self, ins, env):
        op = ins.op
        if op in ('ba.get', 'ba.set', 'list.get', 'list.set') and ins.attrs.get('mode') == 'ck':
            self.index_facts[ins] = self.bounds(env, ins.operands[1])    # for loop versioning
        if op.startswith('cmp.') and self.const(ins.operands[0]) is None or (
                op.startswith('cmp.') and self.const(ins.operands[1]) is None):
            self.decide_cmp(ins, env)
        if op == 'span.set':
            mode = ins.attrs.get('mode')
            if mode in ('ck', 'vck') or ins in self.decision:
                # a byte store has two checks: the index (vck: already proven by licm's guard) and
                # the value; with only the index proven it keeps the value check (vck)
                idx_ok = mode == 'vck' or self.in_bounds(env, ins.operands[0], ins.operands[1], ins)
                byte = ins.operands[0].type == I.T('span', I.T('u8'))
                val_ok = True
                if byte:
                    vlo, vhi = self.bounds(env, ins.operands[2])
                    val_ok = 0 <= vlo and vhi <= 255
                self.decision[ins] = 'nck' if idx_ok and val_ok else 'vck' if idx_ok and byte else 'ck'
            return
        if not ins.results or ins.regions:
            return
        r = ins.results[0]
        if r.type == I.I1:
            env[r] = Fact(0, 1)
            return
        if r.type == I.TINT:
            self.tint_eval(ins, env)
            return
        if r.type != I.I64:
            return
        o = ins.operands
        if op == 'const':
            return
        if op == 'tint.i64':
            # the conversion raises when the value does not fit: afterwards it lies in int64
            lo, hi = self.bounds(env, o[0])
            env[r] = Fact(max(lo, MIN), min(hi, MAX))
            return
        if op in ('add', 'sub', 'mul', 'neg'):
            env[r] = self.arith(ins, env)
            return
        if op == 'zext':
            env[r] = Fact(0, 1)
            return
        if op in ('floordiv', 'floormod'):
            k = self.const(o[1])
            alo, ahi = self.bounds(env, o[0])
            if isinstance(k, int) and not isinstance(k, bool) and k > 0:
                if op == 'floordiv':
                    env[r] = Fact(alo // k, ahi // k)
                else:
                    env[r] = Fact(0, k - 1) if not (0 <= alo and ahi < k) else Fact(alo, ahi)
                if alo >= 0 and k & (k - 1):           # powers of two are rewritten anyway
                    self.decision[ins] = 'nonneg'
                elif ins in self.decision:
                    self.decision[ins] = 'ck'
            elif isinstance(k, int) and not isinstance(k, bool) and k < 0 and op == 'floormod':
                env[r] = Fact(k + 1, 0)
            else:
                blo, bhi = self.bounds(env, o[1])
                if blo >= 1 and alo >= 0:
                    # a non-negative dividend and a divisor known to be >= 1: C's / and % are Python's, and
                    # there is no ZeroDivisionError
                    env[r] = Fact(0, ahi) if op == 'floordiv' else Fact(0, min(ahi, bhi - 1))
                    self.decision[ins] = 'nonneg'
                elif ins in self.decision:
                    self.decision[ins] = 'ck'
            return
        if op == 'and':
            alo, ahi = self.bounds(env, o[0])
            blo, bhi = self.bounds(env, o[1])
            if alo >= 0 and blo >= 0:
                env[r] = Fact(0, min(ahi, bhi))
            elif alo >= 0:
                env[r] = Fact(0, ahi)
            elif blo >= 0:
                env[r] = Fact(0, bhi)
            return
        if op in ('or', 'xor'):
            alo, ahi = self.bounds(env, o[0])
            blo, bhi = self.bounds(env, o[1])
            if alo >= 0 and blo >= 0:
                env[r] = Fact(0, (1 << max(ahi, bhi).bit_length()) - 1)
            return
        if op == 'shr':
            k = self.const(o[1])
            alo, ahi = self.bounds(env, o[0])
            if isinstance(k, int) and 0 <= k < 64:
                env[r] = Fact(alo >> k, ahi >> k)
            return
        if op == 'shl':
            k = self.const(o[1])
            alo, ahi = self.bounds(env, o[0])
            if isinstance(k, int) and 0 <= k < 64 and alo << k >= MIN and ahi << k <= MAX:
                env[r] = Fact(alo << k, ahi << k)
            return
        if op == 'inv':
            alo, ahi = self.bounds(env, o[0])
            env[r] = Fact(-ahi - 1, -alo - 1)
            return
        if op == 'select':
            env[r] = join(self.get(env, o[1]), self.get(env, o[2]))
            return
        if op == 'bytes.get':
            env[r] = Fact(0, 255)
            if ins.attrs.get('mode') == 'ck' or ins in self.decision:
                self.decision[ins] = 'nck' if self.in_bounds(env, o[0], o[1], ins) else 'ck'
            return
        if op in ('span.get', 'list.get') and ins.attrs.get('mode') == 'ck' or (
                op == 'span.get' and ins in self.decision):
            if op == 'span.get':
                self.decision[ins] = 'nck' if self.in_bounds(env, o[0], o[1], ins) else 'ck'
            return
        if op in ('bytes.len', 'list.len', 'span.len'):
            env[r] = Fact(0, LEN_MAX)
            return
        if op == 'call':
            res = self.facts.get('results', {}).get(ins.attrs.get('callee'))
            if res is not None:
                env[r] = Fact(res[0], res[1])
            return

    # ------------------------------------------------------------------ regions
    def region(self, region, env, loops):
        """Analyse `region` under `env` (mutated); returns the env at its `yield`, or None when
        it ends in another terminator."""
        for ins in region.instrs:
            op = ins.op
            if op == 'if':
                self.do_if(ins, env, loops)
                if env is None:
                    return None
                continue
            if op in I.LOOP_OPS:
                self.do_loop(ins, env, loops)
                continue
            if op == 'yield':
                return env
            if op == 'continue':
                loops[-1].continues.append([self.get(env, v) for v in ins.operands])
                return None
            if op == 'break':
                loops[-1].breaks.append([self.get(env, v) for v in ins.operands])
                return None
            if op in ('return', 'unreachable', 'raise', 'reraise'):
                return None
            self.evaluate(ins, env)
            for r in ins.results:
                f = env.get(r)
                self.vfacts[r] = f if f is not None else self.top_for(r)
        return None

    def do_if(self, ins, env, loops):
        c = ins.operands[0]
        outs = []
        yields = []
        for truth, arm in ((True, ins.regions[0]), (False, ins.regions[1])):
            sub = dict(env)
            self.refine(sub, c, truth)
            out = self.region(arm, sub, loops)
            if out is not None:
                outs.append(out)
                yields.append([self.get(out, v) for v in arm.instrs[-1].operands])
        if not outs:
            # nothing falls through: the rest of the region is dead; keep analysing it under the
            # pre-if state (its decisions only matter if it is reachable, which it is not)
            for r in ins.results:
                self.set(env, r, self.top_for(r))
            return
        merged = outs[0]
        if len(outs) == 2:
            a, b = outs
            merged = {k: join(a[k], b[k]) for k in a if k in b}
        env.clear()
        env.update(merged)
        for j, r in enumerate(ins.results):
            f = None
            for y in yields:
                f = join(f, y[j])
            self.set(env, r, f)

    def do_loop(self, ins, env, loops):
        body = ins.regions[0]
        if ins.op == 'for.range':
            lo, hi, step = ins.operands[:3]
            init = ins.operands[3:]
            idx, args = body.args[0], body.args[1:]
        else:
            init, idx, args = ins.operands, None, body.args
        init_facts = [self.get(env, v) for v in init]
        carried = list(init_facts)

        def visit(heads):
            state = _Loop(ins)
            sub = dict(env)
            for a, f in zip(args, heads):
                self.set(sub, a, f)
            if idx is not None and idx.type == I.TINT:
                self.set(sub, idx, self.index_fact(env, lo, hi, step, TOPT))
            elif idx is not None:
                self.set(sub, idx, self.index_fact(env, lo, hi, step))
            self.region(body, sub, loops + [state])
            return state

        rounds = 0
        while True:
            rounds += 1
            state = visit(carried)
            new = list(carried)
            for vals in state.continues:
                new = [join(n, v) for n, v in zip(new, vals)]
            if new == carried:
                break
            if rounds >= WIDEN_AFTER:
                new = [widen(o, n, (-BIG, BIG) if a.type == I.TINT else (MIN, MAX))
                       for o, n, a in zip(carried, new, args)]
            if rounds > 40:          # cannot happen after widening; a guard against a bug
                new = [self.top_for(a) for a in args]
            carried = new
        # Narrowing: `carried` is an invariant of the loop head (every reachable state lies in it), possibly a
        # coarse one after widening. The head state of the next iteration is then contained in
        # join(initial, continues-of-the-body-analysed-under-carried): that is also an invariant, and a tighter
        # one when the guard of the loop caps what the body adds (`while k < n: k += 16`). The last visit
        # must be the one made under the invariant that is kept, because the decisions come from it.
        if args:
            for _ in range(NARROW_ROUNDS):
                cand = list(init_facts)
                for vals in state.continues:
                    cand = [join(n, v) for n, v in zip(cand, vals)]
                if cand == carried or not all(c.lo >= o.lo and c.hi <= o.hi for c, o in zip(cand, carried)):
                    break
                carried = cand
                state = visit(carried)
        for j, r in enumerate(ins.results):
            f = carried[j] if ins.op == 'for.range' else None
            for vals in state.breaks:
                f = join(f, vals[j])
            self.set(env, r, f if f is not None else self.top_for(r))

    def index_fact(self, env, lo, hi, step, top=TOP):
        k = self.const(step)
        llo, lhi = self.bounds(env, lo)
        hlo, hhi = self.bounds(env, hi)
        if k == 1:
            f = Fact(llo, hhi - 1)
            if self.const(hi) is None:
                f.ub[hi] = -1
            if self.const(lo) is None:
                f.lb[lo] = 0
            return f
        if isinstance(k, int) and k > 1:
            return Fact(llo, hhi - 1)
        if isinstance(k, int) and k < 0:
            return Fact(hlo + 1, lhi)
        return top


def run(fn, facts=None):
    """Decide the mode of every checked + - * and unary -, and of // and % by constants."""
    analysis = Analysis(fn, facts)
    env = {}
    params = (facts or {}).get('params') or {}
    for p, n in zip(fn.params, fn.param_names):
        if n in params and p.type == I.I64:
            lo, hi = params[n]
            env[p] = Fact(lo, hi)
    analysis.region(fn.body, env, [])
    fn.index_facts = analysis.index_facts
    folded = 0
    for ins, truth in analysis.cmps.items():
        if truth is not None:
            ins.op, ins.operands, ins.attrs = 'const', [], {'value': bool(truth)}
            folded += 1
    proven = new = 0
    total = 0
    idx_total = idx_new = idx_legacy = 0
    for ins in I.walk(fn.body):
        if ins.op in ('add', 'sub', 'mul', 'neg') and ins.results and ins.result.type == I.I64:
            if ins.attrs.get('mode') == 'ck':
                total += 1
                if analysis.decision.get(ins) == 'nsw':
                    ins.attrs['mode'] = 'nsw'
                    new += 1
            elif ins.attrs.get('mode') == 'nsw':
                proven += 1
        if ins.op in ('floordiv', 'floormod') and analysis.decision.get(ins) == 'nonneg':
            ins.attrs['mode'] = 'nonneg'
        if ins.op in ('bytes.get', 'span.get', 'span.set'):
            if ins.op == 'span.set' and ins.attrs.get('mode') in ('ck', 'vck'):
                idx_total += 1
                d = analysis.decision.get(ins)
                if d == 'nck' or (d == 'vck' and ins.attrs['mode'] == 'ck'):
                    if ins.attrs['mode'] == 'ck':
                        idx_new += 1
                    ins.attrs['mode'] = d
            elif ins.op == 'span.set':
                idx_legacy += 1
            elif ins.attrs.get('mode') == 'ck':
                idx_total += 1
                if analysis.decision.get(ins) == 'nck':
                    ins.attrs['mode'] = 'nck'
                    idx_new += 1
            else:
                idx_legacy += 1
    return {'cmp_folded': folded, 'ck_total': total + proven, 'ck_legacy_proven': proven, 'ck_ssa_proven': new,
            'idx_total': idx_total + idx_legacy, 'idx_legacy_proven': idx_legacy, 'idx_ssa_proven': idx_new}
