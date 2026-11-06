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
* bce s6: a `field.get` is numbered to an earlier one with the same object SSA value and field name
  when no instruction between them may write that field (a `field.set` of the name on any object of
  the struct, a call whose summary may write it or is unknown, an outlined try body); the earlier
  load's facts then apply. A field the whole-program field facts (s4) list as non-negative starts
  at `lo = 0`, and two numbered loads of an immutable `bytes` field name one length.

Only the final (stable) visit of each instruction decides its mode, so every decision holds for
every execution that reaches it.
"""
import json
import os

from .. import effects as E
from .. import ir as I

MIN, MAX = -(1 << 63), (1 << 63) - 1
LEN_MAX = 1 << 48
WIDEN_AFTER = 3

# bce s6: the instructions that may write a struct field without naming it themselves.  A `call`
# (and the container-adopting call forms) writes whatever its effect summary says; an unknown
# summary and an outlined `try` body may write anything.
_CALL_OPS = ('call', 'rt', 'list.call', 'ba.call', 'obj.call', 'list.rt')


def _struct_of(v):
    if v is not None and v.type.head == 'obj' and v.type.args and v.type.args[0].head == 'class':
        return v.type.args[0].name
    return None


def _field_key(ins):
    obj = ins.operands[0]
    name = ins.attrs.get('name')
    cls = ins.attrs.get('cls') or _struct_of(obj)
    return (obj, name, cls)


def _field_kill(ins, fn, defs, summaries):
    """('all', ()) when `ins` may write any struct field, else ((), {(cls, name)})."""
    op = ins.op
    if op == 'try':
        return 'all', ()
    if op == 'field.set':
        obj = ins.operands[0]
        cls = ins.attrs.get('cls') or _struct_of(obj)
        return (), {(cls, ins.attrs.get('name'))}
    if op not in _CALL_OPS:
        return (), ()
    eff = E.instr_effects(ins, fn, None, None, defs, summaries)
    if eff.unknown:
        return 'all', ()
    out = set()
    for loc in eff.writes:
        if loc.startswith('Field(') and loc.endswith(')'):
            cls, _, name = loc[6:-1].partition(',')
            out.add((cls, name))
    return (), out


def number_fields(fn, summaries=None):
    """bce s6: {load: earlier load} for `field.get`s of the same object SSA value and field name
    with no instruction that may write that field on any path between them.

    A `field.set` of the field name on any object of the same struct type is a write (objects may
    alias), and so is a call whose effect summary may write that struct's fields, an unknown call
    and an outlined `try` body.  A loop is iterated to a fixed point: a field entry survives at the
    loop head only if the initial state and every back edge agree on it, so a store anywhere in
    the loop kills it on the back edge.  Nothing survives a loop after it (a `break` path may have
    written), which is conservative and keeps the result independent of the range facts.
    """
    defs = {r: ins for ins in I.walk(fn.body) for r in ins.results}
    canon = {}

    def apply(ins, state):
        op = ins.op
        if op == 'field.get':
            obj, name, _ = _field_key(ins)
            key = (obj, name)
            r = ins.results[0]
            if key in state:
                canon[r] = state[key]
            else:
                canon.pop(r, None)
                state[key] = r
            return
        all_kill, killed = _field_kill(ins, fn, defs, summaries)
        if all_kill:
            state.clear()
            return
        if not killed:
            return
        for key in list(state):
            obj, name = key
            if (_struct_of(obj), name) in killed:
                del state[key]

    def visit(region, state, loops):
        for ins in region.instrs:
            op = ins.op
            if op == 'if':
                arms = []
                for arm in ins.regions:
                    sub = dict(state)
                    out = visit(arm, sub, loops)
                    if out is not None:
                        arms.append(out)
                state.clear()
                if len(arms) == 1:
                    state.update(arms[0])
                elif len(arms) == 2:
                    a, b = arms
                    state.update({k: v for k, v in a.items() if k in b and b[k] is v})
                continue
            if op in I.LOOP_OPS:
                loop(ins, state, loops)
                continue
            if op == 'yield':
                return state
            if op == 'continue':
                if loops:
                    loops[-1].append(dict(state))
                return None
            if op == 'break' or op in ('return', 'unreachable', 'raise', 'reraise'):
                return None
            if op == 'try':
                state.clear()
                for body in ins.regions:          # numbered only among themselves
                    visit(body, {}, loops)
                state.clear()
                continue
            apply(ins, state)
        return None

    def loop(ins, state, loops):
        entry = dict(state)
        for _ in range(50):
            back = []
            out = visit(ins.regions[0], dict(entry), loops + [back])
            if out is not None:
                back.append(out)
            new = {k: v for k, v in entry.items()
                   if back and all(k in b and b[k] is v for b in back)}
            if new == entry:
                break
            entry = new
        state.clear()

    visit(fn.body, {}, [])
    return canon


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


def join(a, b):
    if a is None:
        return b
    if b is None:
        return a
    ub = {w: max(c, b.ub[w]) for w, c in a.ub.items() if w in b.ub}
    lb = {w: min(c, b.lb[w]) for w, c in a.lb.items() if w in b.lb}
    return Fact(min(a.lo, b.lo), max(a.hi, b.hi), ub, lb)


def widen(old, new):
    lo = new.lo if new.lo >= old.lo else MIN
    hi = new.hi if new.hi <= old.hi else MAX
    ub = {w: c for w, c in new.ub.items() if w in old.ub and c <= old.ub[w]}
    lb = {w: c for w, c in new.lb.items() if w in old.lb and c >= old.lb[w]}
    return Fact(lo, hi, ub, lb)


def _clip(lo, hi):
    return max(lo, MIN), min(hi, MAX)


def _negate(pred):
    return {'eq': 'ne', 'ne': 'eq', 'lt': 'ge', 'ge': 'lt', 'le': 'gt', 'gt': 'le'}[pred]


def _swap(pred):
    return {'eq': 'eq', 'ne': 'ne', 'lt': 'gt', 'gt': 'lt', 'le': 'ge', 'ge': 'le'}[pred]


class _Loop(object):
    def __init__(self, ins):
        self.ins = ins
        self.continues = []
        self.breaks = []


class Analysis(object):
    def __init__(self, fn, facts, bce=True):
        self.fn = fn
        self.facts = facts or {}
        self.bce = bce
        self.defs = {r: ins for ins in I.walk(fn.body) for r in ins.results}
        self.decision = {}          # instr -> new mode (final visit wins)
        self.cmps = {}              # cmp instr -> True/False/None (final visit wins)
        self.index_facts = {}       # checked index instr -> (lo, hi) of its index (final visit)
        self.lens = {}
        self.explain = {}           # access instr -> dict for AIL_BCE_EXPLAIN
        self._list_safe = None
        self._names = {}
        # bce s6: field load numbering and the whole-program non-negative fields (s4)
        self.canon = number_fields(fn, self.facts.get('summaries')) if bce else {}
        fields = (self.facts.get('fields') or {}).get('nonneg') or ()
        self.nonneg = frozenset((str(f[0]), str(f[1])) for f in fields if len(f) == 2) if bce else frozenset()

    def vname(self, v):
        n = self._names.get(v)
        if n is None:
            n = v.hint or ('v%d' % len(self._names))
            self._names[v] = n
        return n

    # ------------------------------------------------------------------ facts
    def const(self, v):
        ins = self.defs.get(v)
        if ins is not None and ins.op == 'const':
            return ins.attrs.get('value')
        return None

    def get(self, env, v):
        f = env.get(v)
        if f is None:
            c = self.const(v)
            if isinstance(c, bool):
                return Fact(int(c), int(c))
            if isinstance(c, int):
                return Fact(c, c)
            return TOP
        return f

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
        if v.type in (I.I64, I.I1):
            env[v] = f

    # ------------------------------------------------------------------ bce s3 rules
    def list_lengths_safe(self):
        """Whether every `list.len` in this function sees a length no list op can change."""
        if self._list_safe is not None:
            return self._list_safe
        unsafe = False
        summaries = self.facts.get('summaries') or {}
        changing = ('list.push', 'list.pop', 'list.insert', 'list.del', 'list.clear',
                    'list.extend', 'list.slice', 'list.lit', 'list.move', 'list.copy',
                    'list.share', 'list.rt', 'list.repeat', 'list.reserve',
                    'rec.push', 'rec.pop')
        for ins in I.walk(self.fn.body):
            op = ins.op
            if op in changing:
                unsafe = True
                break
            if op == 'list.reset' and not ins.attrs.get('drop'):
                unsafe = True
                break
            if op in ('call', 'ba.call', 'obj.call', 'list.call'):
                eff = summaries.get(ins.attrs.get('callee'))
                if eff is None or eff.unknown:
                    unsafe = True
                    break
                if any(w.startswith(('Elem(', 'Spine(', 'Rebind(')) for w in eff.writes):
                    unsafe = True
                    break
        self._list_safe = not unsafe
        return self._list_safe

    def upper_steps(self, env, b):
        """Pairs (w, c) with b <= w + c, through up to two symbolic steps."""
        out = []
        fb = self.get(env, b)
        for w, c in fb.ub.items():
            if w is b:
                continue
            out.append((w, c))
            if w in env:
                for w2, c2 in env[w].ub.items():
                    if w2 is not w and w2 is not b:
                        out.append((w2, c + c2))
        return out

    def sum_in_bounds(self, env, base, index):
        """index = a + b, b <= w + c, w = L - a  =>  index <= L + c."""
        d = self.defs.get(index)
        if d is None or d.op != 'add' or d.attrs.get('mode') not in ('ck', 'nsw'):
            return False
        lens = self.lengths_of(base)
        for a, b in ((d.operands[0], d.operands[1]), (d.operands[1], d.operands[0])):
            for w, c in self.upper_steps(env, b):
                dw = self.defs.get(w)
                if dw is not None and dw.op == 'sub' and dw.operands[1] is a:
                    if dw.operands[0] in lens and c <= -1:
                        return True
        return False

    def explain_access(self, ins, env, base, index):
        f = self.get(env, index)
        lo, hi = self.bounds(env, index)
        lens = self.lengths_of(base)
        reason = self.fail_reason(env, base, index, lo, lens)
        return {'fn': self.fn.name, 'op': ins.op,
                'index': {'name': self.vname(index), 'lo': lo, 'hi': hi,
                          'ub': {self.vname(w): c for w, c in f.ub.items()},
                          'lb': {self.vname(w): c for w, c in f.lb.items()}},
                'len': [self.vname(L) for L in lens], 'reason': reason}

    def fail_reason(self, env, base, index, lo, lens):
        if lo < 0:
            return 'index may be negative'
        if base.type.head == 'obj' and base.type.args[0].head == 'list' and not self.list_lengths_safe():
            return 'list length may change (length-changing op or unknown call)'
        if not lens:
            return 'no length value of this container'
        d = self.defs.get(index)
        if d is not None and d.op == 'add':
            for a, b in ((d.operands[0], d.operands[1]), (d.operands[1], d.operands[0])):
                for w, c in self.upper_steps(env, b):
                    dw = self.defs.get(w)
                    if dw is not None and dw.op == 'sub' and dw.operands[1] is a \
                            and dw.operands[0] in lens and c > -1:
                        return 'sum rule needs the offset at most -1'
        return 'no upper bound against a length'

    def join_arms(self, arms):
        """Join the (env, yielded value, fact) triples of the arms of an `if`.  When one arm
        yields a constant and the other's refined env proves the constant is below a bound the
        other arm keeps, keep that symbolic bound (`if maxm > 131 { maxm = 131 }`)."""
        facts = [a[2] for a in arms]
        f = None
        for x in facts:
            f = join(f, x)
        if not self.bce or len(arms) != 2:
            return f
        for ci in (0, 1):
            oi = 1 - ci
            fc = facts[ci]
            if fc.lo != fc.hi or fc.ub or fc.lb:
                continue
            ce, cv, _ = arms[ci]
            oe, ov, fo = arms[oi]
            if self.const(ov) is not None:
                continue
            for w, c in list(fo.ub.items()) + [(ov, 0)]:
                if c < fo.ub.get(w, 0):
                    continue
                if self.le(ce, cv, w, c):
                    f.ub[w] = max(f.ub.get(w, c), c)
            for w, c in list(fo.lb.items()) + [(ov, 0)]:
                if c > fo.lb.get(w, 0):
                    continue
                if self.le(ce, w, cv, -c):
                    f.lb[w] = min(f.lb.get(w, c), c)
        return f

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
        if self.bce and op == 'sub' and a is b:
            self.decide(ins, True)
            return Fact(0, 0)
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

    def lengths_of(self, base):
        """Every length value of `base` that cannot have changed (bytes/span are immutable; a
        list's length only when no list op or call in the function can resize one)."""
        out = self.lens.get(base)
        if out is None:
            out = [r for r, d in self.defs.items()
                   if d.op in ('bytes.len', 'span.len') and d.operands[0] is base]
            if self.bce and base.type == I.BYTES:
                # bce s6: a bytes field is immutable, so numbered loads of it name one length
                rep = self.canon.get(base, base)
                members = {base, rep}
                for d in self.defs.values():
                    if d.op == 'field.get' and d.results and d.result.type == I.BYTES \
                            and self.canon.get(d.result) is rep:
                        members.add(d.result)
                if len(members) > 1:
                    out += [r for r, d in self.defs.items()
                            if d.op == 'bytes.len' and d.operands[0] in members]
            if self.bce and base.type.head == 'obj' and base.type.args[0].head == 'list' \
                    and self.list_lengths_safe():
                out += [r for r, d in self.defs.items()
                        if d.op == 'list.len' and d.operands[0] is base]
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
        if self.bce and self.sum_in_bounds(env, base, index):
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
                if self.bce:
                    if self.decision[ins] == 'ck':
                        self.explain[ins] = self.explain_access(ins, env, ins.operands[0], ins.operands[1])
                    else:
                        self.explain.pop(ins, None)
            return
        if op == 'list.set' and self.bce:
            if ins.attrs.get('mode') == 'ck' or ins in self.decision:
                ok = self.in_bounds(env, ins.operands[0], ins.operands[1], ins)
                self.decision[ins] = 'nck' if ok else 'ck'
                if ok:
                    self.explain.pop(ins, None)
                else:
                    self.explain[ins] = self.explain_access(
                        ins, env, ins.operands[0], ins.operands[1])
            return
        if not ins.results or ins.regions:
            return
        r = ins.results[0]
        if op == 'field.get':
            if r.type == I.I1:
                env[r] = Fact(0, 1)
                return
            if r.type != I.I64:
                return
            same = self.canon.get(r)
            f = self.get(env, same) if same is not None else TOP
            lo, hi, ub, lb = f.lo, f.hi, dict(f.ub), dict(f.lb)
            _, name, cls = _field_key(ins)
            if self.bce and (cls, name) in self.nonneg:
                lo = max(lo, 0)                     # bce s6: a whole-program non-negative field
            env[r] = Fact(lo, hi, ub, lb)
            return
        if r.type == I.I1:
            env[r] = Fact(0, 1)
            return
        if r.type != I.I64:
            return
        o = ins.operands
        if op == 'const':
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
                ok = self.in_bounds(env, o[0], o[1], ins)
                self.decision[ins] = 'nck' if ok else 'ck'
                if self.bce:
                    if ok:
                        self.explain.pop(ins, None)
                    else:
                        self.explain[ins] = self.explain_access(ins, env, o[0], o[1])
            return
        if op in ('span.get', 'list.get') and ins.attrs.get('mode') == 'ck' or (
                op == 'span.get' and ins in self.decision):
            if op == 'span.get':
                ok = self.in_bounds(env, o[0], o[1], ins)
                self.decision[ins] = 'nck' if ok else 'ck'
                if self.bce:
                    if ok:
                        self.explain.pop(ins, None)
                    else:
                        self.explain[ins] = self.explain_access(ins, env, o[0], o[1])
            elif self.bce:
                ok = self.in_bounds(env, o[0], o[1], ins)
                self.decision[ins] = 'nck' if ok else 'ck'
                if ok:
                    self.explain.pop(ins, None)
                else:
                    self.explain[ins] = self.explain_access(ins, env, o[0], o[1])
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
                yields.append([(out, v, self.get(out, v)) for v in arm.instrs[-1].operands])
        if not outs:
            # nothing falls through: the rest of the region is dead; keep analysing it under the
            # pre-if state (its decisions only matter if it is reachable, which it is not)
            for r in ins.results:
                self.set(env, r, TOP)
            return
        merged = outs[0]
        if len(outs) == 2:
            a, b = outs
            merged = {k: join(a[k], b[k]) for k in a if k in b}
        env.clear()
        env.update(merged)
        for j, r in enumerate(ins.results):
            self.set(env, r, self.join_arms([y[j] for y in yields]))

    def loop_edges(self, loop):
        out = []

        def walk(region):
            for ins in region.instrs:
                if ins.op in ('continue', 'break'):
                    out.append(ins)
                elif ins.op in I.LOOP_OPS:
                    continue
                elif ins.op == 'if':
                    for r in ins.regions:
                        walk(r)
        walk(loop.regions[0])
        return out

    def nondec(self, value, base, env, depth=0):
        """Whether `value` is `base` plus a non-negative amount, through if/loop joins."""
        if value is base:
            return True
        if depth > 16:
            return False
        d = self.defs.get(value)
        if d is None:
            return False
        op = d.op
        if op == 'add':
            x, y = d.operands
            if x is base or self.nondec(x, base, env, depth + 1):
                return self.bounds(env, y)[0] >= 0
            if y is base or self.nondec(y, base, env, depth + 1):
                return self.bounds(env, x)[0] >= 0
            return False
        if op == 'select':
            return (self.nondec(d.operands[1], base, env, depth + 1)
                    and self.nondec(d.operands[2], base, env, depth + 1))
        if op == 'if':
            try:
                idx = d.results.index(value)
            except ValueError:
                return False
            for r in d.regions:
                term = r.instrs[-1]
                if term.op == 'yield':
                    if not self.nondec(term.operands[idx], base, env, depth + 1):
                        return False
                elif term.op not in ('break', 'continue', 'return', 'raise', 'reraise', 'unreachable'):
                    return False
            return True
        if op == 'loop':
            try:
                idx = d.results.index(value)
            except ValueError:
                return False
            return self.loop_result_nondecreasing(d, idx, base, env, depth + 1)
        return False

    def loop_result_nondecreasing(self, loop, idx, base, env, depth):
        if depth > 16 or loop.op != 'loop' or idx >= len(loop.operands):
            return False
        init = loop.operands[idx]
        if not (init is base or self.nondec(init, base, env, depth + 1)):
            return False
        arg = loop.regions[0].args[idx]
        for edge in self.loop_edges(loop):
            if idx >= len(edge.operands) or not self.nondec(edge.operands[idx], arg, env, depth + 1):
                return False
        return True

    def do_loop(self, ins, env, loops):
        body = ins.regions[0]
        if ins.op == 'for.range':
            lo, hi, step = ins.operands[:3]
            init = ins.operands[3:]
            idx, args = body.args[0], body.args[1:]
        else:
            init, idx, args = ins.operands, None, body.args
        carried = [self.get(env, v) for v in init]
        if self.bce and ins.op == 'loop':
            edges = [e for e in self.loop_edges(ins) if e.op == 'continue']
            for j, initv in enumerate(init):
                if j >= len(carried) or initv.type != I.I64:
                    continue
                if all(j < len(e.operands) and self.nondec(e.operands[j], args[j], env)
                       for e in edges):
                    f = carried[j]
                    f.lb[initv] = max(f.lb.get(initv, 0), 0)
                    f.lo = max(f.lo, self.get(env, initv).lo)
        rounds = 0
        while True:
            rounds += 1
            state = _Loop(ins)
            sub = dict(env)
            for a, f in zip(args, carried):
                self.set(sub, a, f)
            if idx is not None:
                self.set(sub, idx, self.index_fact(env, lo, hi, step))
            self.region(body, sub, loops + [state])
            new = list(carried)
            for vals in state.continues:
                new = [join(n, v) for n, v in zip(new, vals)]
            if new == carried:
                break
            if rounds >= WIDEN_AFTER:
                new = [widen(o, n) for o, n in zip(carried, new)]
            if rounds > 40:          # cannot happen after widening; a guard against a bug
                new = [TOP for _ in new]
            carried = new
        for j, r in enumerate(ins.results):
            f = carried[j] if ins.op == 'for.range' else None
            for vals in state.breaks:
                f = join(f, vals[j])
            self.set(env, r, f if f is not None else TOP)

    def index_fact(self, env, lo, hi, step):
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
        return TOP


def _bce_enabled():
    return os.environ.get('AIL_BCE', '1').strip().lower() not in ('0', 'off', 'no', 'false')


def dump_explain(fn):
    """AIL_BCE_EXPLAIN=path: one JSON line per access the last ranges run left checked."""
    target = os.environ.get('AIL_BCE_EXPLAIN')
    if not target:
        return
    for rec in getattr(fn, '_range_explain', ()):
        with open(target, 'a') as handle:
            handle.write(json.dumps(rec, sort_keys=True) + '\n')


def run(fn, facts=None):
    """Decide the mode of every checked + - * and unary -, and of // and % by constants."""
    analysis = Analysis(fn, facts, bce=_bce_enabled())
    env = {}
    params = (facts or {}).get('params') or {}
    for p, n in zip(fn.params, fn.param_names):
        if n in params and p.type == I.I64:
            lo, hi = params[n]
            env[p] = Fact(lo, hi)
    analysis.region(fn.body, env, [])
    fn.index_facts = analysis.index_facts
    fn._range_explain = list(analysis.explain.values())
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
        if ins.op in ('bytes.get', 'span.get', 'span.set', 'list.get', 'list.set'):
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
