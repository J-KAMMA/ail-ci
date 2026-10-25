"""Symbolic bounds of an index inside a loop, for loop versioning (licm.py, part 3).

The range pass proves an index in range when its bound is a constant or one SSA value plus a
constant. Grid code indexes with sums of loop-invariant row offsets and column indices:

    up = ((y + h - 1) % h) * w;  ...  for x in range(w): cur[up + x], cur[mid + xl[x]]

Nothing here proves `up + x < len(cur)`; it gives the loop a runtime guard that is cheap (once per
entry of the loop) and implies every such access is in range:

    up >= 0 and up + w - 1 < len(cur) and mid + w - 1 < len(cur) and ...

A bound is a set of *forms* `const + sum(coeff * atom)`, where an atom is an i64 SSA value defined in
front of the loop (so the guard can compute it there). A set of lower forms means "the value is at
least the smallest of these"; a set of upper forms, "at most the largest". The rules:

* a constant is itself; a value defined in front of the loop is an atom;
* the index of a `for.range` with a positive constant step inside the loop (or the loop's own) lies in
  [lo, hi - 1], with the bounds of `lo` and `hi`;
* `add`, `sub`, `neg` and `mul` by a constant combine the bounds exactly (the operation is `nsw` or
  `ck`: its result, when there is one, is the mathematical value; `wrap` is not used);
* `floormod a, m` lies in [0, m - 1] when m > 0 (a constant, a divisor the range pass proved >= 1
  (mode `nonneg`), or else with the side condition `m - 1 >= 0` added to the guard);
* `zext` is in [0, 1]; `and` with a non-negative constant mask c is in [0, c];
* `select` and the results of an `if` take the union of their alternatives; an `if` arm's yield is
  refined by the arm's condition when it compares the yielded value itself (`xl = x - 1; if xl < 0:
  xl = w - 1` gives [0, w - 1] on the fall-through arm and `w - 1` on the other);
* an element read of a list the function owns lies within the bounds of every value ever stored into
  that list (`list.repeat`, `list.set`, `list.push`, `span.set`), when every use of the list is one of
  those or a read, and the bounds are in atoms that dominate the loop (top-level values of the body
  before the statement holding it).

* `mul` of two values whose lower bounds are >= 0 (constants, or side conditions in the guard) lies
  between the products of their bounds; a monomial has at most two atoms (`h*w`: the guard of a row
  loop over a grid of `w*h` cells is then `h*w - 1 < len(cur)`, once per sweep).

Every form keeps at most TERMS_MAX monomials with coefficients up to COEF_MAX and a constant up to
CONST_MAX, and the guard first checks |atom| <= ATOM_MAX for every atom it uses (ATOM2_MAX for an atom
of a product), so its own arithmetic (done in `wrap` mode) cannot overflow:
8 * 2^10 * max(2^40, 2^24 * 2^24) + 2^40 < 2^62.
"""
from .. import ir as I
from .. import effects as E

ATOM_MAX = 1 << 40
ATOM2_MAX = 1 << 24
COEF_MAX = 1 << 10
CONST_MAX = 1 << 40
TERMS_MAX = 8
SET_MAX = 4

_READS = ('list.get', 'list.len', 'span.get', 'span.len', 'span.of', 'spec.get')


class Form(object):
    """const + sum(coeff * monomial); `terms` is a tuple of (monomial, coeff), a monomial being a tuple
    of one or two atoms (ordered by their keys), the terms ordered by their monomials."""
    __slots__ = ('const', 'terms')

    def __init__(self, const, terms=()):
        self.const = const
        self.terms = tuple(terms)

    @property
    def sig(self):
        return tuple((tuple(id(a) for a in m), k) for m, k in self.terms)

    @property
    def atoms(self):
        out = []
        for m, _ in self.terms:
            for a in m:
                if not any(a is b for b in out):
                    out.append(a)
        return out

    @property
    def degree(self):
        return max([len(m) for m, _ in self.terms] or [0])

    def ok(self):
        return (abs(self.const) <= CONST_MAX and len(self.terms) <= TERMS_MAX and self.degree <= 2
                and all(abs(k) <= COEF_MAX for _, k in self.terms))

    def __repr__(self):
        return 'Form(%d%s)' % (self.const, ''.join(' %+d*%s' % (k, '*'.join(a.hint or '?' for a in m))
                                                   for m, k in self.terms))


class Bounds(object):
    """Bounds of i64 values in terms of atoms: the values not in `inside` (defined in front of the
    region analysed). `order` gives every value a stable key (the forms, and so the guard's C, do not
    depend on object ids). `elements(base)` gives the bounds of the elements of a container, or None."""

    def __init__(self, fn, inside, defs, order, elements=None):
        self.fn = fn
        self.inside = inside
        self.defs = defs
        self.order = order
        self.elements = elements
        self.memo = {}
        self.loop_of = {}
        for ins in I.walk(fn.body):
            if ins.op == 'for.range':
                self.loop_of[ins.regions[0].args[0]] = ins

    # ------------------------------------------------------------------ forms
    def const(self, v):
        for _ in range(8):
            d = self.defs.get(v)
            if d is not None and d.op in ('tint.from', 'tint.i64', 'tint.i64sat'):
                v = d.operands[0]
                continue
            if d is not None and d.op == 'const':
                c = d.attrs.get('value')
                if isinstance(c, int) and not isinstance(c, bool):
                    return c
            return None
        return None

    def atom(self, v):
        return Form(0, [((v,), 1)])

    def mkey(self, m):
        return tuple(self.order.get(a, 0) for a in m)

    def collect(self, const, pairs):
        """A form from (monomial, coeff) pairs, like terms summed."""
        terms = {}
        for m, k in pairs:
            m = tuple(sorted(m, key=lambda a: self.order.get(a, 0)))
            key = tuple(id(a) for a in m)
            if key in terms:
                terms[key][1] += k
            else:
                terms[key] = [m, k]
        items = sorted(((m, k) for m, k in terms.values() if k), key=lambda t: self.mkey(t[0]))
        return Form(const, items)

    def add(self, f, g, sign=1):
        return self.collect(f.const + sign * g.const, list(f.terms) + [(m, sign * k) for m, k in g.terms])

    def scale(self, f, k):
        return Form(f.const * k, [(m, c * k) for m, c in f.terms] if k else [])

    def product(self, f, g):
        if f.degree + g.degree > 2:
            return Form(CONST_MAX + 1)            # not ok(): rejected by norm
        pairs = [(m, k * g.const) for m, k in f.terms] + [(m, k * f.const) for m, k in g.terms]
        pairs += [(m1 + m2, k1 * k2) for m1, k1 in f.terms for m2, k2 in g.terms]
        return self.collect(f.const * g.const, pairs)

    def norm(self, forms, low):
        """One form per monomial signature (the smallest constant for a lower set, the largest for an
        upper one); None when the set is too large or a form exceeds the limits."""
        best = {}
        for f in forms:
            if not f.ok():
                return None
            s = f.sig
            if s not in best or (f.const < best[s].const if low else f.const > best[s].const):
                best[s] = f
        out = sorted(best.values(), key=lambda f: ([self.mkey(m) for m, _ in f.terms], f.const))
        return out if len(out) <= SET_MAX else None

    def cross(self, xs, ys, low, sign=1):
        return self.norm([self.add(x, y, sign) for x in xs for y in ys], low)

    # ------------------------------------------------------------------ bounds
    def of(self, v):
        """(lows, highs, conds) or None: v >= min(lows), v <= max(highs) whenever it is computed and
        every form in conds is >= 0 (side conditions the guard must check)."""
        if v in self.memo:
            return self.memo[v]
        self.memo[v] = None              # cycles (loop-carried values) have no bound
        r = self.compute(v)
        if r is not None and (r[0] is None or r[1] is None):
            r = None
        self.memo[v] = r
        return r

    def compute(self, v):
        if v.type not in (I.I64, I.TINT):
            return None
        c = self.const(v)
        if c is not None:
            return [Form(c)], [Form(c)], []
        if v not in self.inside:
            return [self.atom(v)], [self.atom(v)], []
        loop = self.loop_of.get(v)
        if loop is not None:
            lo, hi, step = loop.operands[:3]
            k = self.const(step)
            if k is None or k <= 0:
                return None
            bl, bh = self.of(lo), self.of(hi)
            if bl is None or bh is None:
                return None
            return bl[0], self.norm([Form(h.const - 1, h.terms) for h in bh[1]], False), bl[2] + bh[2]
        d = self.defs.get(v)
        if d is None:
            return None
        op = d.op
        if op.startswith('tint.'):
            op = op[5:]
            if op.endswith('_i64'):
                op = op[:-4]
        elif op in ('add', 'sub', 'mul', 'neg', 'floormod') and d.attrs.get('mode') == 'wrap':
            return None
        if op in ('from', 'i64', 'i64sat'):
            return self.of(d.operands[0])
        if op in ('add', 'sub'):
            a, b = self.of(d.operands[0]), self.of(d.operands[1])
            if a is None or b is None:
                return None
            if op == 'add':
                return self.cross(a[0], b[0], True), self.cross(a[1], b[1], False), a[2] + b[2]
            return self.cross(a[0], b[1], True, -1), self.cross(a[1], b[0], False, -1), a[2] + b[2]
        if op == 'neg':
            a = self.of(d.operands[0])
            if a is None:
                return None
            return self.norm([self.scale(f, -1) for f in a[1]], True), \
                self.norm([self.scale(f, -1) for f in a[0]], False), a[2]
        if op == 'mul':
            x, y = d.operands
            k = self.const(y)
            if k is None:
                x, y = y, x
                k = self.const(y)
            if k is None:
                a, b = self.of(x), self.of(y)
                if a is None or b is None:
                    return None
                conds = a[2] + b[2]
                for f in a[0] + b[0]:
                    if f.terms:
                        conds.append(f)          # both factors >= 0: the product is monotone in each
                    elif f.const < 0:
                        return None
                return self.norm([self.product(p, q) for p in a[0] for q in b[0]], True), \
                    self.norm([self.product(p, q) for p in a[1] for q in b[1]], False), conds
            a = self.of(x)
            if a is None:
                return None
            lows, highs = (a[0], a[1]) if k >= 0 else (a[1], a[0])
            return self.norm([self.scale(f, k) for f in lows], True), \
                self.norm([self.scale(f, k) for f in highs], False), a[2]
        if op == 'floormod':
            m = d.operands[1]
            k = self.const(m)
            if k is not None:
                return ([Form(0)], [Form(k - 1)], []) if k > 0 else None
            bm = self.of(m)
            if bm is None:
                return None
            conds = list(bm[2])
            if not d.op.startswith('tint.') and d.attrs.get('mode') != 'nonneg':
                # m >= 1, checked by the guard (otherwise the result may be negative, or it raised)
                conds += [Form(f.const - 1, f.terms) for f in bm[0]]
            return [Form(0)], self.norm([Form(f.const - 1, f.terms) for f in bm[1]], False), conds
        if op == 'zext':
            return [Form(0)], [Form(1)], []
        if op == 'and':
            for x in d.operands:
                k = self.const(x)
                if k is not None and k >= 0:
                    return [Form(0)], [Form(k)], []
            return None
        if op == 'select':
            return self.union([self.of(d.operands[1]), self.of(d.operands[2])])
        if op == 'if':
            j = d.results.index(v)
            alts = []
            for truth, arm in ((True, d.regions[0]), (False, d.regions[1])):
                last = arm.instrs[-1] if arm.instrs else None
                if last is None or last.op != 'yield':
                    continue                 # the arm does not fall through: no value from it
                yv = last.operands[j]
                alts.append(self.refined(yv, d.operands[0], truth))
            return self.union(alts) if alts else None
        if op in ('span.get', 'list.get') and self.elements is not None:
            return self.elements(d.operands[0])
        return None

    def union(self, alts):
        if not alts or any(a is None for a in alts):
            return None
        lows = self.norm([f for a in alts for f in a[0]], True)
        highs = self.norm([f for a in alts for f in a[1]], False)
        if lows is None or highs is None:
            return None
        return lows, highs, [c for a in alts for c in a[2]]

    def refined(self, yv, cond, truth):
        """The bounds of `yv` where the i1 `cond` is `truth` (a direct comparison of yv itself)."""
        base = self.of(yv)
        d = self.defs.get(cond)
        cop = d.op if d is not None else ''
        if cop.startswith('tint.'):
            cop = 'cmp.' + cop[5:]
        if cop.endswith('_i64'):
            cop = cop[:-4]
        kinds = (I.I64, I.TINT)
        if base is None or d is None or not cop.startswith('cmp.') \
                or d.operands[0].type not in kinds or d.operands[1].type not in kinds:
            return base
        pred = cop[4:]
        if not truth:
            pred = {'eq': 'ne', 'ne': 'eq', 'lt': 'ge', 'ge': 'lt', 'le': 'gt', 'gt': 'le'}[pred]
        a, b = d.operands
        if b is yv and a is not yv:
            a, b = b, a
            pred = {'eq': 'eq', 'ne': 'ne', 'lt': 'gt', 'gt': 'lt', 'le': 'ge', 'ge': 'le'}[pred]
        if a is not yv:
            return base
        other = self.of(b)
        if other is None:
            return base
        lows, highs, conds = base
        if pred in ('ge', 'gt', 'eq'):
            k = 1 if pred == 'gt' else 0
            lows = _better(lows, [Form(f.const + k, f.terms) for f in other[0]], True)
        if pred in ('le', 'lt', 'eq'):
            k = 1 if pred == 'lt' else 0
            highs = _better(highs, [Form(f.const - k, f.terms) for f in other[1]], False)
        return lows, highs, conds + (other[2] if (lows is not base[0] or highs is not base[1]) else [])


def _better(old, new, low):
    """Both sets bound the same value; keep the one that makes the cheaper and likelier guard:
    constant forms beat symbolic ones, between constant sets the tighter one, and otherwise the
    refinement (`new`: the arm's own test, e.g. `y + 1 < h` gives h - 1 where the operands give h)."""
    def const_only(fs):
        return all(not f.terms for f in fs)
    if const_only(old) and not const_only(new):
        return old
    if const_only(new) and const_only(old):
        bn = min(f.const for f in new) if low else max(f.const for f in new)
        bo = min(f.const for f in old) if low else max(f.const for f in old)
        return new if (bn > bo if low else bn < bo) else old
    return new


def value_order(fn):
    """A stable key for every value of `fn` (parameters, then definitions and block arguments in
    program order)."""
    order = {}
    for p in fn.params:
        order[p] = len(order)

    def region(r):
        for a in r.args:
            order[a] = len(order)
        for ins in r.instrs:
            for res in ins.results:
                order[res] = len(order)
            for sub in ins.regions:
                region(sub)
    region(fn.body)
    return order


class ElementFacts(object):
    """Bounds of the elements of the lists `fn` owns, in atoms defined at the top level of its body
    (None for a list with a use that may store an element the analysis cannot bound)."""

    def __init__(self, fn, defs, order):
        self.fn = fn
        self.defs = defs
        self.order = order
        top = set(fn.params)
        for ins in fn.body.instrs:
            top.update(ins.results)
        self.inside = set(order) - top
        self.top_index = {}
        for k, ins in enumerate(fn.body.instrs):
            for res in ins.results:
                self.top_index[res] = k
        self.bounds = Bounds(fn, self.inside, defs, order)
        self.cache = {}

    def root(self, v):
        d = self.defs.get(v)
        if d is not None and d.op == 'span.of':
            v = d.operands[0]
        r = E._root(v, self.fn, self.defs)
        return r if r.startswith('Own(') else None

    def of_root(self, root):
        if root in self.cache:
            return self.cache[root]
        self.cache[root] = None
        names = set(v for v, d in self.defs.items() if d.op in ('list.ref', 'span.of') and self.root(v) == root)
        alts = []
        for ins in I.walk(self.fn.body):
            used = [k for k, v in enumerate(ins.operands) if v in names]
            if not used:
                continue
            op = ins.op
            if op in _READS and used == [0]:
                continue
            if op == 'list.copy' and used == [1]:
                continue                     # copied from: a read
            if op in ('list.repeat', 'list.push') and used == [0]:
                alts.append(self.bounds.of(ins.operands[1]))
            elif op in ('list.set', 'span.set') and used == [0]:
                alts.append(self.bounds.of(ins.operands[2]))
            elif op == 'list.reset' and used == [0]:
                continue
            else:
                return None
        if not alts:
            return None
        facts = self.bounds.union(alts)
        self.cache[root] = facts
        return facts

    def for_loop(self, loop):
        """`elements(base)` for a guard in front of `loop`: element bounds whose atoms are top-level
        values defined before the top-level statement that holds `loop`."""
        stmt = None
        for k, top in enumerate(self.fn.body.instrs):
            if top is loop or any(i is loop for r in top.regions for i in I.walk(r)):
                stmt = k
                break
        params = set(self.fn.params)

        def elements(base):
            root = self.root(base)
            if root is None or stmt is None:
                return None
            facts = self.of_root(root)
            if facts is None:
                return None
            for f in facts[0] + facts[1] + facts[2]:
                for a in f.atoms:
                    if a not in params and self.top_index.get(a, stmt) >= stmt:
                        return None
            return facts
        return elements
