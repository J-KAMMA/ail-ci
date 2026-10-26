# -*- coding: utf-8 -*-
"""unified.py -- AIL_UNIFIED=1 prototype: type inference and unboxing on the general path
(docs/design/UNIFIED_IR.md).

The general path (pyboxed2.py) accepts the program as it is and gives every value the boxed
representation (`ail_obj` in a GC-rooted frame slot, every operation a runtime call). This pass
runs before the general path emits any function and proves, for each local variable of each
function it can analyse, one of

    int    an int64 (the general path's own int: an overflow is the same AIL_LIMIT stop)
    float  a C double (the general path heap-boxes every float)
    bool   a C int 0/1
    obj    anything else: stays boxed, as today

A proven variable lives in a C local instead of a frame slot; operations whose operands are
all proven are emitted as C (with the general runtime's own checks: overflow, division by
zero, shifts); everything else is the general path's code, unchanged. Boxing happens at the
edges: a proven value read where a boxed one is needed (a call argument, a container element,
print) is boxed there (`ail_box_int` does not allocate, `ail_box_float` does); a value whose
result type is fixed by the language (`len()`, `not`, `in`, `int()`, ...) is computed boxed and
unboxed.

Top-level functions whose every reference is a direct positional call also get their
parameters and result specialised from the types at their call sites (one specialisation per
function: the join of every call site; one boxed call site makes the parameter boxed).

The analysis is a forward abstract interpretation over a flat lattice, run to a whole-program
fixed point: bottom (no information yet) < int, float, bool < obj (widened). A variable's
storage is the join of every value assigned to it (one representation per variable for the
whole function), and a variable is only unboxed when every read of it is definitely assigned
(an unbound read must still raise UnboundLocalError, which only the frame slot can tell).

Anything the emitter reaches that this pass did not plan for (a name read through a path that
bypasses the hooks) raises `Conflict`; pyboxed2.build() then demotes that variable or function to
boxed and compiles again. With AIL_UNIFIED=0 nothing here runs and the C is the general path's (default on since 2026-10-21).

Step 2 (UNIFIED_IR.md §9): the draws of random.Random have their result types (`_DRAWS`; a float draw
whose value lands in a C double is drawn without a box, randrt.RNG_U); the element types of lists
come from unified_lists.py, solved again in every round of the fixed point, and give C reads of
`xs[i]`, vector loops over lists of scalars, and static arrays for constant tables (`_subscript`,
`_vector_loop`, `_const_loop`); `a, b = x, y` and `x in (2, 3)` are emitted as C.
"""
import ast
import os

import pyfunc

from pyfront import int_constant

INT, FLOAT, BOOL, OBJ = 'int', 'float', 'bool', 'obj'
BOT = None
SCALAR = (INT, FLOAT, BOOL)
CTYPE = {INT: 'int64_t', FLOAT: 'double', BOOL: 'int'}
KIND = {INT: 'int', FLOAT: 'float', BOOL: 'bool'}       # pyboxed2's own kind names
_I64_MIN, _I64_MAX = -(1 << 63), (1 << 63) - 1
_EXACT = 1 << 53


def enabled():
    # default on since 2026-10-21 (UNIFIED_IR.md section 14); AIL_UNIFIED=0 / off / no / false is the opt-out
    return os.environ.get('AIL_UNIFIED', '').strip().lower() not in ('0', 'off', 'no', 'false')


_NAN_WORDS = ('nan', 'inf', 'infinity')


def nan_capable(tree):
    """C117: a NaN or an infinity can be made by the program (`float("nan")`, `math.nan`, `math.inf`,
    `isnan`; a NaN made only by arithmetic on an overflowed value or parsed from data, C118, is not seen here: `float_search_risk` covers it). NaN is the one float where a copy is not the same value:
    CPython's container and dataclass `==`, `in`, `count`, `index` and dict lookup take `a is b` as equal
    before they compare, so `W(nan) == W(nan)` is True when both hold the one object, and an unboxed
    double is boxed afresh at each store. A program like that keeps its floats boxed (no plan)."""
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant):
            v = n.value
            if isinstance(v, str):
                t = v.strip().lower().lstrip('+-')
                if t in _NAN_WORDS:
                    return True
        elif isinstance(n, ast.Attribute) and n.attr in ('nan', 'inf', 'isnan', 'isinf', 'isfinite'):
            return True
        elif isinstance(n, ast.Name) and n.id in ('nan', 'inf', 'isnan', 'isinf', 'isfinite'):
            return True
        elif isinstance(n, ast.ImportFrom) and n.module == 'math' and any(
                a.name in ('nan', 'inf', 'isnan', 'isinf', 'isfinite') for a in n.names):
            return True
    return False


class Conflict(Exception):
    """The emitter reached a proven variable (or a specialised function) through a path this pass
    does not handle: build() demotes `key` ((function, variable) or (function, '*')) and retries."""

    def __init__(self, key, why=''):
        Exception.__init__(self, '%s: %s' % (key, why))
        self.key = key
        _REASONS.append('%s:%s %s' % (key[0], key[1], why))


_REASONS = []


def join(a, b):
    if a is BOT:
        return b
    if b is BOT:
        return a
    return a if a == b else OBJ


STATS = []          # one dict per compiled program (AIL_UNIFIED_STATS=path appends JSON lines)


# ============================================================================== the analysis

class FnPlan(object):
    def __init__(self, name, info, node):
        self.name = name                 # key: the C name (unique across functions and methods)
        self.info = info
        self.node = node
        self.params = list(info['params'])
        self.locals = set()              # every local name of the function
        self.bad = set()                 # locals that stay boxed whatever their values
        self.vtype = {}                  # local -> lattice value
        self.spec = False                # parameters / result specialised
        self.ptypes = [OBJ] * len(self.params)
        self.ret = OBJ
        self.calls_in = []               # (caller plan or None, call node)
        self.own_updates = []            # `own` filtered to the shapes the fixed point's round reads
        self.own_returns = []            # `own` filtered to its `return` statements

    def unboxed(self, name):
        t = self.vtype.get(name)
        return t in SCALAR and name not in self.bad

    def cvar(self, name):
        return 'u_' + name


def _parents(node):
    par = {}
    for p in ast.walk(node):
        for c in ast.iter_child_nodes(p):
            par[id(c)] = p
    return par


def _is_range_call(n, plan_names):
    return (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'range'
            and 'range' not in plan_names and 1 <= len(n.args) <= 3 and not n.keywords
            and not any(isinstance(a, ast.Starred) for a in n.args))


def _own_nodes(fn):
    """The nodes of `fn`'s own scope: not the bodies of nested lambdas / defs / classes."""
    out = []
    stack = list(fn.body)
    while stack:
        n = stack.pop()
        out.append(n)
        if isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(n))
    return out


def _always_returns(stmts):
    for s in stmts:
        if isinstance(s, (ast.Return, ast.Raise)):
            return True
        if isinstance(s, ast.If) and s.orelse and _always_returns(s.body) and _always_returns(s.orelse):
            return True
    return False


ALL = object()      # the definitely-assigned set after a statement that does not complete


def _inter(a, b):
    if a is ALL:
        return b
    if b is ALL:
        return a
    return a & b


class _DefAssign(object):
    """Definite assignment over a function body: every local read where it may be unbound."""

    def __init__(self, locals_):
        self.locals = locals_
        self.maybe = set()

    def reads(self, node, assigned):
        if node is None:
            return
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in self.locals:
                if assigned is not ALL and n.id not in assigned:
                    self.maybe.add(n.id)

    def targets(self, t):
        return {n.id for n in ast.walk(t) if isinstance(n, ast.Name)}

    def block(self, stmts, assigned):
        for s in stmts:
            if assigned is ALL:
                return ALL
            assigned = self.stmt(s, assigned)
        return assigned

    def stmt(self, s, a):
        if isinstance(s, ast.Assign):
            self.reads(s.value, a)
            for t in s.targets:
                if not isinstance(t, ast.Name):
                    self.reads(t, a)
            return a | set().union(*[self.targets(t) for t in s.targets])
        if isinstance(s, ast.AnnAssign):
            self.reads(s.value, a)
            return a | self.targets(s.target) if s.value is not None else a
        if isinstance(s, ast.AugAssign):
            self.reads(s.value, a)
            self.reads(ast.Name(id=s.target.id, ctx=ast.Load()) if isinstance(s.target, ast.Name) else s.target, a)
            return a | self.targets(s.target)
        if isinstance(s, ast.If):
            self.reads(s.test, a)
            return _inter(self.block(s.body, set(a)), self.block(s.orelse, set(a)))
        if isinstance(s, ast.While):
            self.reads(s.test, a)
            self.block(s.body, set(a))
            self.block(s.orelse, set(a))
            return a
        if isinstance(s, ast.For):
            self.reads(s.iter, a)
            self.block(s.body, a | self.targets(s.target))
            self.block(s.orelse, set(a))
            return a
        if isinstance(s, (ast.Return, ast.Raise)):
            for c in ast.iter_child_nodes(s):
                self.reads(c, a)
            return ALL
        if isinstance(s, (ast.Break, ast.Continue)):
            return ALL
        if isinstance(s, ast.Try):
            body = self.block(s.body, set(a))
            body = self.block(s.orelse, body) if body is not ALL else ALL
            out = body
            for h in s.handlers:
                out = _inter(out, self.block(h.body, set(a)))
            if s.finalbody:
                self.block(s.finalbody, set(a))
            return a if out is ALL else out
        if isinstance(s, ast.With):
            for item in s.items:
                self.reads(item.context_expr, a)
            body = self.block(s.body, set(a))
            return a if body is ALL else body
        if isinstance(s, ast.Match):
            self.reads(s.subject, a)
            for case in s.cases:
                self.block(case.body, set(a))
            return a
        # anything else (Expr, Assert, Delete, Pass, Global, ...): reads with `a`, no new binding
        for c in ast.iter_child_nodes(s):
            if isinstance(c, ast.expr):
                self.reads(c, a)
        return a


def _has_float(plan):
    return (any(t == FLOAT for t in plan.gconst.values())
            or any(t == FLOAT for fp in plan.fns.values() for t in fp.vtype.values())
            or any(sp.ret == FLOAT or FLOAT in sp.ptypes for sp in plan.spec.values())
            or any(v == FLOAT for v in plan.lstate.values())
            or any(v == FLOAT for v in plan.lelem.values())
            or bool(plan.draws))


_STR_FUNCS = ('str', 'repr', 'len', 'int', 'bool', 'chr', 'ord', 'hex', 'bin', 'oct', 'format', 'ascii', 'id', 'hash',
              'isinstance', 'callable')
_PASS_FUNCS = ('list', 'tuple', 'set', 'frozenset', 'sorted', 'reversed')       # hold what their argument holds
_STR_METHODS = frozenset(('upper', 'lower', 'strip', 'lstrip', 'rstrip', 'split', 'rsplit', 'splitlines', 'join',
                          'format', 'replace', 'title', 'capitalize', 'zfill', 'center', 'ljust', 'rjust', 'encode',
                          'decode', 'startswith', 'endswith', 'isdigit', 'isalpha', 'isalnum', 'isspace', 'swapcase',
                          'partition', 'removeprefix', 'removesuffix', 'casefold', 'expandtabs'))
# uses of a list name that cannot add a value to it or let another name do so
_READ_METHODS = frozenset(('count', 'index', 'copy', 'join', 'startswith', 'endswith', 'keys', 'values', 'items'))
_READ_CALLS = ('len', 'print', 'sorted', 'list', 'tuple', 'set', 'str', 'repr', 'sum', 'min', 'max', 'any', 'all',
               'reversed', 'enumerate', 'zip', 'isinstance', 'bool')
_FREE_ANN = ('str', 'bytes', 'int', 'bool')
_STR_LISTS = frozenset(('split', 'rsplit', 'splitlines', 'partition'))


class _Free(object):
    """Which values of one program can never be a float (so a search with them cannot depend on the identity of a NaN):
    scalars (constants, f-strings, int / bool values, the results of `str` methods and the locals that only ever hold
    such values) and flat containers of scalars (displays, `.split()`, `list(...)` of one, and the locals that only
    ever hold those AND are only read: never appended to, stored into, passed on or aliased)."""

    def __init__(self, plan, comp):
        self.plan = plan
        self.comp = comp
        self.cache = {}                   # fp name -> (scalar names, flat names)

    def sets(self, fp):
        if fp.name not in self.cache:
            self.cache[fp.name] = self._solve(fp)
        return self.cache[fp.name]

    def free(self, e, fp):
        """True when `e` can only be a float-free scalar or a flat float-free container."""
        sc, fl = self.sets(fp) if fp is not None else (set(), set())
        return self.cont(e, fp, sc, fl) or self.elem(e, fp, sc, fl)

    def elem(self, e, fp, sc, fl):
        if isinstance(e, ast.Constant):
            return not isinstance(e.value, (float, complex))
        if isinstance(e, ast.JoinedStr):
            return True
        if isinstance(e, ast.Name):
            return e.id in sc
        if isinstance(e, ast.IfExp):
            return self.elem(e.body, fp, sc, fl) and self.elem(e.orelse, fp, sc, fl)
        if isinstance(e, ast.BinOp):
            return isinstance(e.op, (ast.Add, ast.Mult, ast.Mod)) and self.elem(e.left, fp, sc, fl) \
                and self.elem(e.right, fp, sc, fl)
        if isinstance(e, ast.Subscript) and not isinstance(e.slice, ast.Slice):
            return self.cont(e.value, fp, sc, fl)           # an element of a flat container
        if isinstance(e, ast.Call) and not e.keywords and not any(isinstance(a, ast.Starred) for a in e.args):
            f = e.func
            if isinstance(f, ast.Name) and _builtin(self.plan, fp, f.id) and f.id in _STR_FUNCS:
                return True
            if isinstance(f, ast.Attribute) and f.attr in _STR_METHODS and f.attr not in _STR_LISTS \
                    and f.attr not in self.comp.user_method_names \
                    and not (isinstance(f.value, ast.Name) and f.value.id in self.plan.not_receivers):
                return True
        if fp is not None and isinstance(e, ast.expr):
            return etype(self.plan, fp, e, lambda nm: _name_type(self.plan, fp, nm)) in (INT, BOOL)
        return False

    def cont(self, e, fp, sc, fl):
        if isinstance(e, (ast.List, ast.Tuple, ast.Set)):
            return all(not isinstance(x, ast.Starred) and self.elem(x, fp, sc, fl) for x in e.elts)
        if isinstance(e, ast.Dict):
            return all(k is not None and self.elem(k, fp, sc, fl) and self.elem(v, fp, sc, fl)
                       for k, v in zip(e.keys, e.values))
        if isinstance(e, ast.Name):
            return e.id in fl or e.id in sc
        if isinstance(e, ast.Subscript) and isinstance(e.slice, ast.Slice):
            return self.cont(e.value, fp, sc, fl)
        if isinstance(e, ast.BinOp):
            return isinstance(e.op, (ast.Add, ast.Mult)) and self.cont(e.left, fp, sc, fl) \
                and (self.cont(e.right, fp, sc, fl) or self.elem(e.right, fp, sc, fl))
        if isinstance(e, ast.Call) and not e.keywords and not any(isinstance(a, ast.Starred) for a in e.args):
            f = e.func
            if isinstance(f, ast.Name) and _builtin(self.plan, fp, f.id) and f.id in _PASS_FUNCS:
                return all(self.cont(a, fp, sc, fl) for a in e.args)
            if isinstance(f, ast.Attribute) and f.attr in _STR_LISTS and f.attr not in self.comp.user_method_names \
                    and not (isinstance(f.value, ast.Name) and f.value.id in self.plan.not_receivers):
                return True
        return False

    def _solve(self, fp):
        par = _parents(fp.node)
        stores = {nm: [] for nm in fp.locals}        # name -> ('v', value) | ('e', iterable) | None (not followed)
        annots = {x.arg: x.annotation for x in fp.node.args.args}
        for p in fp.params:
            a = annots.get(p)
            if not (isinstance(a, ast.Name) and a.id in _FREE_ANN):
                stores[p].append(None)
        loadbad = set()
        for n in fp.own:
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)) and n.id in stores:
                q = par.get(id(n))
                if isinstance(q, ast.Assign) and n in q.targets:
                    stores[n.id].append(('v', q.value))
                elif isinstance(q, ast.AnnAssign) and q.target is n and q.value is not None:
                    stores[n.id].append(('v', q.value))
                elif isinstance(q, ast.AugAssign) and q.target is n and isinstance(q.op, (ast.Add, ast.Mult)):
                    stores[n.id].append(('v', q.value) if isinstance(q.op, ast.Mult) else ('a', q.value))
                elif isinstance(q, (ast.For, ast.comprehension)) and q.target is n:
                    stores[n.id].append(('e', q.iter))
                else:
                    stores[n.id].append(None)
            elif isinstance(n, (ast.ExceptHandler, ast.Import, ast.ImportFrom, ast.MatchAs, ast.MatchStar, ast.MatchMapping)):
                dumped = ast.dump(n)
                for nm in stores:
                    if nm in dumped:
                        stores[nm].append(None)
            elif isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for x in ast.walk(n):
                    if isinstance(x, ast.Name) and x.id in stores:
                        stores[x.id].append(None)       # read by code with a scope of its own: not followed
            elif isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name) and n.target.id in stores:
                stores[n.target.id].append(None)
        for n in fp.own:
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in stores:
                q = par.get(id(n))
                if isinstance(q, ast.Compare):
                    continue
                if isinstance(q, ast.Subscript) and q.value is n and isinstance(q.ctx, ast.Load):
                    continue
                if isinstance(q, ast.For) and q.iter is n:
                    continue
                if isinstance(q, ast.Call) and n in q.args and isinstance(q.func, ast.Name) \
                        and q.func.id in _READ_CALLS and _builtin(self.plan, fp, q.func.id):
                    continue
                if isinstance(q, ast.Attribute) and q.value is n and q.attr in _READ_METHODS:
                    continue
                if isinstance(q, ast.FormattedValue):
                    continue
                loadbad.add(n.id)
        # scalars: every store is a scalar (immutable: any read is fine)
        sc = {nm for nm, v in stores.items() if v and None not in v}
        changed = True
        while changed:
            changed = False
            for nm in sorted(sc):
                for st in stores[nm]:
                    kind, v = st
                    ok = self.elem(v, fp, sc, set()) if kind in ('v', 'a') else self.cont(v, fp, sc, set())
                    if not ok:
                        sc.discard(nm)
                        changed = True
                        break
        # flat containers: only read, every store is a container of scalars
        fl = {nm for nm, v in stores.items() if v and None not in v and nm not in sc and nm not in loadbad}
        changed = True
        while changed:
            changed = False
            for nm in sorted(fl):
                for kind, v in stores[nm]:
                    if kind == 'e' or not self.cont(v, fp, sc, fl):
                        fl.discard(nm)
                        changed = True
                        break
        return sc, fl


_SEARCH_METHODS = ('count', 'index', 'remove', 'get', 'pop', 'setdefault', 'discard')


def _site(n, what):
    try:
        text = ast.unparse(n)[:60]
    except Exception:
        text = '?'
    return '%s: %s' % (what, text)


def float_search_risk(plan, tree, comp):
    """C118/C119: the program searches a container (`count`, `index`, `remove`, `in`, `not in`, `==`, `!=` between
    objects) with a value that may be a float. CPython takes `a is b` as equal before `==`, so a NaN found by
    identity needs the one box it was stored with; an unboxed double is boxed afresh at each store. A NaN made by
    arithmetic or parsed from data cannot be ruled out by name, so such a program keeps every float boxed.
    A scalar operand (int / float / bool proven) of `==` cannot be a container, and a constant that is not a float
    is never NaN."""
    owner = {}
    for fp in plan.fns.values():
        for n in fp.own:
            owner[id(n)] = fp

    free = _Free(plan, comp)

    def t(n):
        fp = owner.get(id(n))
        if fp is None:
            return OBJ
        return etype(plan, fp, n, lambda nm: _name_type(plan, fp, nm))

    def ff(n):
        # cannot be a float, nor hold one
        return free.free(n, owner.get(id(n)))

    ann = set()
    user = getattr(comp, 'user_top', None)

    def own_code():
        # the program's own statements: not the preludes and libraries the compiler adds, nor the `__eq__` a
        # @dataclass generates (reached only through a comparison written in the program, which is scanned)
        for top in tree.body:
            if getattr(top, '_ail_safety', False):
                continue
            name = getattr(top, 'name', '')
            if isinstance(top, (ast.FunctionDef, ast.ClassDef)) and (
                    (user is not None and (type(top).__name__, name) not in user) or name.startswith('_ail')):
                continue                # added by the compiler
            stack = [top]
            while stack:
                x = stack.pop()
                if getattr(x, '_ail_gen', False):
                    continue
                yield x
                for note in (getattr(x, 'annotation', None), getattr(x, 'returns', None)):
                    if note is not None:
                        ann.update(id(m) for m in ast.walk(note))      # `dict[str, float]` is a type, not a lookup
                stack.extend(ast.iter_child_nodes(x))

    for n in own_code():
        if id(n) in ann:
            continue
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _SEARCH_METHODS \
                and n.args and not isinstance(n.args[0], ast.Starred):
            if not ff(n.args[0]) and not ff(n.func.value):
                return _site(n, '.%s(...)' % n.func.attr)
        elif isinstance(n, ast.Subscript) and not isinstance(n.slice, ast.Slice) and (
                t(n.slice) == FLOAT or (isinstance(n.slice, ast.Tuple) and any(t(e) not in (INT, BOOL) for e in n.slice.elts))
                or (isinstance(n.slice, ast.Call) and isinstance(n.slice.func, ast.Name) and n.slice.func.id in comp.classes)):
            return _site(n, 'a dict lookup')         # a dict lookup by a float, a tuple or an instance (a list index by a float is a TypeError)
        elif isinstance(n, ast.Compare):
            sides = [n.left] + list(n.comparators)
            for i, o in enumerate(n.ops):
                a, b = sides[i], sides[i + 1]
                if isinstance(o, (ast.In, ast.NotIn)):
                    if not ff(a) and not ff(b):
                        return _site(n, 'in')
                elif isinstance(o, (ast.Eq, ast.NotEq)):
                    if ff(a) or ff(b):
                        continue            # a float-free side: nothing on the other side can be found by identity
                    if isinstance(a, ast.Name) and isinstance(b, ast.Name) and a.id == b.id:
                        continue            # `x != x`: one object compares as itself, a NaN test is a scalar test
                    if t(a) in SCALAR or t(b) in SCALAR:
                        continue
                    return _site(n, '== / !=')
    return None


_CONSUME_FUNCS = ('print', 'str', 'repr', 'int', 'bool', 'round', 'format', 'divmod', 'pow', 'len')
_LOOPS = (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _ancestors(par, n, stop):
    x = par.get(id(n))
    while x is not None and x is not stop:
        yield x
        x = par.get(id(x))


def float_escape_demotes(plan, tree, comp):
    """C118/C119, the narrow form of `float_search_risk`: the float locals whose unboxed value may reach a
    container search with the identity of a NaN lost. An unboxed double is boxed afresh at every point where an
    object is needed, so a NaN that gets boxed twice (or whose object is shared with another name) is two objects.
    Only a local that is boxed at such a point matters; a double that is read by arithmetic, an ordering comparison,
    `print`, an f-string, an `int()` or a `math` function never makes a box that outlives the read.
    The locals are grouped in classes by the copies between them (`a = b`, `a = b if c else d`, an argument passed
    to an unboxed parameter, `float(a)`, `max(a, b)`, `+a`); a class may stay unboxed when no name of it is boxed
    ("escapes"), or when exactly one point boxes it, once per call (not in a loop), and the value is made in the
    function (not a parameter, not read from a boxed object). Returns the (function, local) pairs to keep boxed,
    or None when this form of proof does not apply: a float read out of a typed list or tuple (a copy of the
    element, boxed afresh) that is boxed again, or a read this pass cannot place. The lists and tuples that are
    searched keep their float elements boxed (unified_lists `floatguard`, set by the marker in the result)."""
    parent, taint, esc = {}, {}, {}

    def find(k):
        while parent.setdefault(k, k) != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[a] = b
            taint[b] = max(taint.get(b, 0), taint.get(a, 0))
            esc[b] = esc.get(b, []) + esc.get(a, [])

    def mark_taint(k, kind=1):
        # 1: a value that came in from outside (a parameter, a boxed object); 2: a copy read out of a typed container
        r = find(k)
        taint[r] = max(taint.get(r, 0), kind)

    def float_name(fp, nm):
        return nm in fp.locals and fp.vtype.get(nm) == FLOAT and nm not in fp.bad

    for fp in plan.fns.values():
        for v in fp.locals:
            if float_name(fp, v):
                find((fp.name, v))
    if not parent:
        return set()

    for fp in plan.fns.values():
        par = _parents(fp.node)
        env = (lambda fp: lambda nm: _name_type(plan, fp, nm))(fp)

        def numeric(e):
            return etype(plan, fp, e, env) in (INT, FLOAT, BOOL)

        def leaves(e, out):
            """The expressions an object may be handed back from, through the forms that return an operand."""
            if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.UAdd):
                leaves(e.operand, out)
            elif isinstance(e, ast.IfExp):
                leaves(e.body, out)
                leaves(e.orelse, out)
            elif isinstance(e, ast.BoolOp):
                for x in e.values:
                    leaves(x, out)
            elif isinstance(e, ast.NamedExpr):
                leaves(e.value, out)
            elif isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in ('float', 'min', 'max', 'abs') \
                    and not e.keywords and _builtin(plan, fp, e.func.id) \
                    and not any(isinstance(a, ast.Starred) for a in e.args):
                for a in e.args:
                    leaves(a, out)
            else:
                out.append(e)
            return out

        def feed(target, value):
            """The float local `target` receives `value`."""
            k = (fp.name, target)
            for lf in leaves(value, []):
                if isinstance(lf, ast.Constant) or isinstance(lf, (ast.BinOp, ast.Compare, ast.JoinedStr)) \
                        or (isinstance(lf, ast.UnaryOp)):
                    continue
                if isinstance(lf, ast.Name):
                    if float_name(fp, lf.id):
                        union(k, (fp.name, lf.id))
                    elif etype(plan, fp, lf, env) in (INT, BOOL):
                        pass
                    else:
                        mark_taint(k, 1)
                    continue
                if isinstance(lf, ast.Call) and isinstance(lf.func, ast.Name):
                    if lf.func.id in plan.spec and (fp.name, id(lf)) not in plan.generic_sites:
                        continue                # a result made in the callee: its own box
                    if _builtin(plan, fp, lf.func.id) and lf.func.id in ('int', 'round', 'len', 'ord', 'bool'):
                        continue
                if _draw_of(plan, lf) is not None:
                    continue
                mark_taint(k, 2)

        for p in fp.params:
            if float_name(fp, p):
                mark_taint((fp.name, p))
        for n in fp.own:
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and float_name(fp, n.id):
                q = par.get(id(n))
                if isinstance(q, ast.Assign) and any(t is n for t in q.targets):
                    feed(n.id, q.value)
                elif isinstance(q, ast.AnnAssign) and q.target is n and q.value is not None:
                    feed(n.id, q.value)
                elif isinstance(q, ast.AugAssign) and q.target is n:
                    pass                            # a new object
                elif isinstance(q, ast.Tuple) and isinstance(par.get(id(q)), ast.Assign) \
                        and isinstance(par[id(q)].value, ast.Tuple) \
                        and len(par[id(q)].value.elts) == len(q.elts) and par[id(q)].targets[0] is q \
                        and not any(isinstance(e, ast.Starred) for e in par[id(q)].value.elts):
                    feed(n.id, par[id(q)].value.elts[q.elts.index(n)])
                else:
                    mark_taint((fp.name, n.id), 2)          # a loop variable, an unpacked element
        # arguments passed to an unboxed parameter are copies of the callee's parameter
        for n in fp.own:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in plan.spec:
                sp = plan.spec[n.func.id]
                if (fp.name, id(n)) in plan.generic_sites or len(n.args) != len(sp.params):
                    continue
                for a, pn, pt in zip(n.args, sp.params, sp.ptypes):
                    if pt == FLOAT and float_name(sp, pn):
                        for lf in leaves(a, []):
                            if isinstance(lf, ast.Name) and float_name(fp, lf.id):
                                union((fp.name, lf.id), (sp.name, pn))
                            elif not isinstance(lf, (ast.Constant, ast.BinOp, ast.UnaryOp)):
                                mark_taint((sp.name, pn), 2)
        # the reads
        for n in fp.own:
            tread = isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load) \
                and plan.lstate.get((fp.name, id(n))) == FLOAT        # a typed read: a copy of an element
            if not (tread or (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and float_name(fp, n.id))):
                continue
            child = n
            while True:
                p = par.get(id(child))
                if isinstance(p, ast.UnaryOp) and isinstance(p.op, ast.UAdd) \
                        or isinstance(p, ast.IfExp) and child is not p.test \
                        or isinstance(p, (ast.BoolOp, ast.NamedExpr)) \
                        or (isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and child in p.args
                            and p.func.id in ('float', 'min', 'max', 'abs') and not p.keywords
                            and _builtin(plan, fp, p.func.id)
                            and not any(isinstance(a, ast.Starred) for a in p.args)):
                    child = p
                    continue
                break
            consumed = False
            once = False
            if p is None:
                pass
            elif isinstance(p, (ast.UnaryOp, ast.FormattedValue, ast.Expr)):
                consumed = True
            elif isinstance(p, (ast.If, ast.While, ast.IfExp, ast.Assert)) and getattr(p, 'test', None) is child:
                consumed = True
            elif isinstance(p, ast.BinOp):
                consumed = numeric(p.left) and numeric(p.right)
            elif isinstance(p, ast.Compare):
                consumed = not any(isinstance(o, (ast.In, ast.NotIn, ast.Is, ast.IsNot)) for o in p.ops) \
                    and all(numeric(x) for x in [p.left] + p.comparators)
            elif isinstance(p, (ast.Assign, ast.AnnAssign)) and p.value is child:
                tg = p.targets if isinstance(p, ast.Assign) else [p.target]
                consumed = all(isinstance(t, ast.Name) and float_name(fp, t.id) for t in tg)
            elif isinstance(p, ast.Tuple) and isinstance(par.get(id(p)), ast.Assign) and par[id(p)].value is p \
                    and isinstance(par[id(p)].targets[0], ast.Tuple) and len(par[id(p)].targets) == 1 \
                    and len(par[id(p)].targets[0].elts) == len(p.elts):
                t = par[id(p)].targets[0].elts[p.elts.index(child)]
                consumed = isinstance(t, ast.Name) and float_name(fp, t.id)
            elif isinstance(p, ast.AugAssign) and p.value is child:
                consumed = isinstance(p.target, ast.Name) and float_name(fp, p.target.id) \
                    and isinstance(p.op, _ARITH + (ast.Div, ast.FloorDiv, ast.Mod))
            elif isinstance(p, ast.Return):
                once = True
            elif isinstance(p, ast.Call) and child in p.args and not any(isinstance(a, ast.Starred) for a in p.args):
                f = p.func
                if isinstance(f, ast.Name):
                    if f.id in plan.spec and (fp.name, id(p)) not in plan.generic_sites:
                        sp = plan.spec[f.id]
                        i = p.args.index(child)
                        consumed = len(p.args) == len(sp.params) and sp.ptypes[i] == FLOAT
                    elif f.id in _CONSUME_FUNCS and _builtin(plan, fp, f.id):
                        consumed = all(numeric(a) for a in p.args) or f.id in ('print', 'str', 'repr', 'format')
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == 'math' \
                        and 'math' not in fp.locals and 'math' not in comp.classes and 'math' not in comp.functions:
                    consumed = all(numeric(a) for a in p.args)
            if tread:
                if consumed and not any(isinstance(x, _LOOPS[3:] + (ast.Lambda,)) for x in _ancestors(par, n, fp.node)):
                    continue
                return None
            if consumed:
                continue
            loop = False
            if not once:
                x = par.get(id(n))
                while x is not None and x is not fp.node:
                    if isinstance(x, _LOOPS):
                        loop = True
                        break
                    x = par.get(id(x))
            esc.setdefault(find((fp.name, n.id)), []).append(loop)
    # a class is unsafe when it has an escape and is tainted, has two or more, or has one inside a loop
    bad = set()
    for k in list(parent):
        r = find(k)
        e = esc.get(r, [])
        if e and (taint.get(r, 0) or len(e) > 1 or any(e)):
            if taint.get(r, 0) == 2:
                return None
            bad.add(k)
    out = {('<float>', 'search')}
    for fname, v in bad:
        fp = plan.fns.get(fname)
        out.add((fp.info['cname'] if fp is not None and fp.spec else fname, v))
    return out


class Plan(object):
    """The whole-program result: the FnPlans by C name, the specialised functions by Python name,
    the module constants."""

    def __init__(self):
        self.fns = {}            # cname -> FnPlan
        self.spec = {}           # python name of a specialised top-level function -> FnPlan
        self.gconst = {}         # module constant name -> lattice value
        self.need_generic = set()  # specialised functions whose boxed body is still reachable
        self.stats = {}


def analyze(comp, tree, demote, nofloat=False):
    """`comp` is the pyboxed2 Compiler with every function and class registered.
    `nofloat`: no value is proven float (C118: see `float_search_risk`)."""
    plan = Plan()
    plan.nofloat = nofloat
    plan.float_guard = ('<float>', 'search') in (demote or ())       # C118: searched lists / tuples keep their floats boxed
    names_all = set(comp.functions)
    plan.fn_names = set(comp.functions)
    plan.module_names = (set(comp.module_names) | set(comp.from_imports) | set(comp.module_aliases)
                         | set(comp.classes))
    plan.draws = _native_draws(comp) if os.environ.get('AIL_UNIFIED_DRAWS') != '0' else {}
    plan.not_receivers = set(comp.module_aliases) | set(comp.from_imports) | {'math', 'sys', 'dict'} | set(comp.classes)
    demote = set(demote or ())
    plan.id_callees = _identity_callees(tree, names_all)     # C101

    # ---- module constants: one top-level `NAME = <int/float/bool literal>`, never stored elsewhere
    stores = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            stores[n.id] = stores.get(n.id, 0) + 1
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            for nm in n.names:
                stores[nm] = stores.get(nm, 0) + 2
    for s in tree.body:
        tgt = val = None
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name):
            tgt, val = s.targets[0].id, s.value
        elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name) and s.value is not None:
            tgt, val = s.target.id, s.value
        if tgt is None or stores.get(tgt) != 1 or tgt in comp.functions or tgt in comp.classes:
            continue
        neg = False
        if isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub):
            neg, val = True, val.operand
        if isinstance(val, ast.Constant):
            v = val.value
            if isinstance(v, bool):
                if not neg:
                    plan.gconst[tgt] = BOOL
            elif isinstance(v, int) and _I64_MIN <= (-v if neg else v) <= _I64_MAX:
                plan.gconst[tgt] = INT
            elif isinstance(v, float) and not nofloat:
                plan.gconst[tgt] = FLOAT
    plan.gconst = {k: v for k, v in plan.gconst.items() if ('<module>', k) not in demote}
    # ---- module tables: `NAME = <tuple/list display of int constants or of int tuples>`, stored once and only
    # ever read as the iterable of a for loop (nothing else can reach the object to change it)
    plan.ctables = {}
    dyn = any(isinstance(n, ast.Name) and n.id in ('globals', 'vars', 'eval', 'exec') for n in ast.walk(tree))
    # one id(node)->parent map for the whole tree, built once: `_parents(node)` per function is the
    # same mapping restricted to that function's subtree (a node's parent does not change), and the
    # table scan below needs it too. Walking every function body separately was a second walk per
    # function on top of the one `_own_nodes` already does.
    par_all = _parents(tree)
    if not dyn and ('<module>', '<tables>') not in demote:
        loads = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                p = par_all.get(id(n))
                loads.setdefault(n.id, []).append(isinstance(p, ast.For) and p.iter is n)
        for s in tree.body:
            tgt = val = None
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name):
                tgt, val = s.targets[0].id, s.value
            elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name) and s.value is not None:
                tgt, val = s.target.id, s.value
            if tgt is None or stores.get(tgt) != 1 or tgt in comp.functions or tgt in comp.classes:
                continue
            if isinstance(val, (ast.Tuple, ast.List)) and loads.get(tgt) and all(loads[tgt]) \
                    and _table_rows(val.elts) is not None:
                plan.ctables[tgt] = val.elts

    # ---- the functions this pass analyses
    infos = [(name, info) for name, info in comp.functions.items()]
    for cname in comp.class_order:
        for mname, info in comp.classes[cname]['methods'].items():
            infos.append((info['cname'], info))
    for key, info in infos:
        node = info['node']
        cname = info['cname']
        if (cname, '*') in demote or info.get('generator') or info.get('lru_cache'):
            continue
        own = _own_nodes(node)
        if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Yield, ast.YieldFrom,
                              ast.Await)) for n in own):
            continue
        if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id in ('locals', 'vars', 'eval', 'exec', 'globals') for n in own):
            continue
        fp = FnPlan(cname, info, node)
        fp.is_method = info.get('is_method', False)
        fp.pyname = node.name
        par = par_all
        params = set(info['all_params'])
        assigned = set()
        for n in own:
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                assigned.add(n.id)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                assigned.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                assigned.update((a.asname or a.name).split('.')[0] for a in n.names)
            elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
                assigned.add(n.name)
            elif isinstance(n, ast.MatchMapping) and n.rest:
                assigned.add(n.rest)
        globals_ = set()
        for n in own:
            if isinstance(n, (ast.Global, ast.Nonlocal)):
                globals_.update(n.names)
        fp.locals = (params | assigned) - globals_
        fp.bad = set(globals_)
        # binding sites this pass can lower; any other one keeps the name boxed
        for n in own:
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                p = par.get(id(n))
                ok = False
                if isinstance(n.ctx, ast.Store):
                    if isinstance(p, ast.Assign) and any(t is n for t in p.targets):
                        ok = True
                    elif isinstance(p, ast.AnnAssign) and p.target is n and p.value is not None:
                        ok = True
                    elif isinstance(p, ast.AugAssign) and p.target is n:
                        ok = True
                    elif isinstance(p, ast.For) and p.target is n and _is_range_call(p.iter, names_all):
                        ok = True
                    elif isinstance(p, ast.For) and p.target is n and (
                            const_rows(plan, fp, p.iter, 1) or _local_iter(fp, p.iter)):
                        ok = True
                    elif isinstance(p, ast.Tuple) and _pair_assign(par.get(id(p))):
                        ok = True
                    elif isinstance(p, ast.Tuple) and all(isinstance(e, ast.Name) for e in p.elts):
                        gp = par.get(id(p))
                        ok = (isinstance(gp, ast.For) and gp.target is p
                              and (const_rows(plan, fp, gp.iter, len(p.elts)) is not None
                                   or _local_iter(fp, gp.iter) or _is_zip(gp.iter, len(p.elts), names_all)
                                   or _is_enum(gp.iter, len(p.elts), names_all))) \
                            or (_unpackable(gp) and gp.targets[0] is p)
                if not ok:
                    fp.bad.add(n.id)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                fp.bad.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                fp.bad.update((a.asname or a.name).split('.')[0] for a in n.names)
            elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
                fp.bad.add(n.name)
            elif isinstance(n, ast.MatchMapping) and n.rest:
                fp.bad.add(n.rest)
            elif isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                fp.bad.update(x.id for x in ast.walk(n) if isinstance(x, ast.Name))
        # the parameters that are not plain positional ones (keyword-only, *args, **kwargs) stay boxed
        fp.bad.update(set(info['all_params']) - set(info['params']))
        da = _DefAssign(fp.locals)
        da.block(node.body, set(params))
        fp.bad |= da.maybe
        fp.bad |= {v for (f, v) in demote if f == cname}
        fp.bad |= _identity_names(own)
        for v in fp.locals:
            fp.vtype[v] = OBJ if v in fp.bad else BOT
        fp.own = own
        # The fixed point's round below only ever acts on assignments, `for` targets and `return`s; the
        # rest of `own` was walked and re-dispatched on every one of the up-to-200 rounds for nothing.
        fp.own_updates = [n for n in own
                          if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For))]
        fp.own_returns = [n for n in own if isinstance(n, ast.Return)]
        # the locals unified_lists.py does not follow (bound in a way it does not model, or seen by nested code)
        lbad = set()
        for n in own:
            if isinstance(n, ast.ExceptHandler) and n.name:
                lbad.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                lbad.update((a.asname or a.name).split('.')[0] for a in n.names)
            elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
                lbad.add(n.name)
            elif isinstance(n, ast.MatchMapping) and n.rest:
                lbad.add(n.rest)
            elif isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name):
                lbad.add(n.target.id)
            elif isinstance(n, ast.withitem) and n.optional_vars is not None:
                lbad.update(x.id for x in ast.walk(n.optional_vars) if isinstance(x, ast.Name))
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Del):
                lbad.add(n.id)
            elif isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                lbad.update(x.id for x in ast.walk(n) if isinstance(x, ast.Name))
        fp.lbad = (lbad | set(info['all_params']) - set(info['params'])) & fp.locals
        # row variables: `for r in TABLE:` (the front end lowers `for a, b in TABLE` to this) where r is bound
        # nowhere else and every read of r is `r[c]`, c an int constant, inside the loop body: r[c] is the table's
        fp.rowvars = {}
        stores_in = {}
        for n in own:
            if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load):
                stores_in[n.id] = stores_in.get(n.id, 0) + 1
        for n in own:
            if not (isinstance(n, ast.For) and isinstance(n.target, ast.Name)):
                continue
            r = n.target.id
            if stores_in.get(r) != 1 or r in fp.lbad or r in globals_ or r in info['all_params']:
                continue
            inside = {id(x) for s in n.body for x in ast.walk(s)}
            ok = True
            for x in own:
                if isinstance(x, ast.Name) and x.id == r and isinstance(x.ctx, ast.Load):
                    p = par.get(id(x))
                    if id(x) not in inside or not (isinstance(p, ast.Subscript) and p.value is x
                                                   and isinstance(p.ctx, ast.Load) and _int_const(p.slice) is not None):
                        ok = False
                        break
            if ok:
                fp.rowvars[r] = n
        plan.fns[cname] = fp

    # ---- specialised variants. A top-level function with plain positional parameters gets, beside its
    # boxed body (still called by every boxed caller), a second body `pfu_<name>` with unboxed parameters and
    # result, for the types its analysed direct call sites pass. The boxed body starts with a guard: when the
    # arguments it receives carry those types it calls the specialised body (so a call from module code, a
    # generator, map(f, ...) or a function value also gets it); otherwise it runs as today.
    for name, info in comp.functions.items():
        base = plan.fns.get(info['cname'])
        if base is None or info['kwonly'] or info['vararg'] or info['kwarg'] or info['defaults']:
            continue
        if info['node'].decorator_list or name in comp.module_names or name in getattr(comp, 'mix_typed', {}):
            continue
        if not info['params'] and not _always_returns(info['node'].body):
            continue
        if any(isinstance(n, (ast.Try, ast.With)) for n in base.own):
            continue        # a return through a finally keeps its value in a frame slot
        if ('pfu_' + name, '*') in demote or name in plan.id_callees:
            continue
        # a local of some function with the same name would make the call go elsewhere
        if any(name in p.locals for p in plan.fns.values()):
            continue
        sp = FnPlan('pfu_' + name, info, info['node'])
        sp.is_method = False
        sp.pyname = name
        sp.locals = set(base.locals)
        sp.bad = set(base.bad) | {v for (f, v) in demote if f == sp.name}
        sp.vtype = {v: (OBJ if v in sp.bad else BOT) for v in sp.locals}
        sp.own = base.own
        sp.own_updates = base.own_updates
        sp.own_returns = base.own_returns
        sp.lbad = set(base.lbad)
        sp.rowvars = dict(base.rowvars)
        sp.spec = True
        sp.ptypes = [BOT] * len(sp.params)
        sp.ret = BOT
        # a parameter annotation is a hint, not a proof: it is used only when no analysed call site says more,
        # and the entry guard of the boxed body checks it on every call that comes in boxed
        sp.hints = [OBJ if (plan.nofloat and h == FLOAT) else h
                    for h in (_ann_type(a.annotation) for a in info['node'].args.args)]
        plan.fns[sp.name] = sp
        plan.spec[name] = sp
    plan.generic_sites = set()       # (caller C name, id(call)): calls that go to the boxed body
    owner = {}
    for fp in plan.fns.values():
        for n in fp.own:
            owner.setdefault(id(n), []).append(fp)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in plan.spec:
            sp = plan.spec[n.func.id]
            if n.keywords or len(n.args) != len(sp.params) or any(isinstance(a, ast.Starred) for a in n.args):
                for caller in owner.get(id(n), []):
                    plan.generic_sites.add((caller.name, id(n)))
                continue
            for caller in owner.get(id(n), []):
                sp.calls_in.append((caller, n))

    # ---- closed functions (unified_lists.py): every reference is a positional call of the right arity in a body
    # this pass analyses, so the classes of its parameters and of its result are those of the call sites
    plan.closed = {}
    plan.lkey = {}
    plan.lstate = {}
    plan.ltab = {}
    plan.lelem = {}
    plan.lvar = {}
    plan.lcomps = {}        # node -> the component types of a proven tuple ('int' / 'float' / 'bool' / 'obj' / 'bot')
    plan.lecomps = {}       # node -> the same for the elements of a proven list whose elements are all such tuples
    # AIL_UNIFIED_LISTS=0 / AIL_UNIFIED_DRAWS=0: measurement only (which step a difference comes from)
    plan.lists_on = ('<module>', '<lists>') not in demote and os.environ.get('AIL_UNIFIED_LISTS') != '0'
    if plan.lists_on:
        for name, info in comp.functions.items():
            if info['cname'] not in plan.fns or info['kwonly'] or info['vararg'] or info['kwarg'] or info['defaults']:
                continue
            if info['node'].decorator_list or name in comp.module_names or name in getattr(comp, 'mix_typed', {}):
                continue
            if name.startswith('_ail') or name in getattr(comp, 'prelude_names', ()) or stores.get(name):
                continue
            if any(name in p.locals for p in plan.fns.values()):
                continue
            plan.closed[name] = len(info['params'])
        callee_ids = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in plan.closed:
                callee_ids.add(id(n.func))
                if id(n) not in owner or n.keywords or len(n.args) != plan.closed[n.func.id] \
                        or any(isinstance(a, ast.Starred) for a in n.args):
                    plan.closed.pop(n.func.id, None)
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and n.id in plan.closed and id(n) not in callee_ids:
                plan.closed.pop(n.id, None)
    plan.const_iter = lambda it, k, fp=None: ('int' if const_rows(plan, fp, it, k) else None)
    plan.is_builtin = lambda fp, name: _builtin(plan, fp, name)
    plan.table_rows = _table_rows
    plan.row_read = lambda fp, n: _row_read(plan, fp, n)

    def lists_round():
        """Solve the list classes for the current scalar types; True when the published states changed."""
        if not plan.lists_on:
            return False
        import unified_lists
        plan.lkey = {}
        cons = []
        for fp in plan.fns.values():
            env = env_of(fp)
            # a local whose class holds only scalars of one type (a parameter of a closed function that every call
            # site passes an int, ...) has that type for the constraints even where unified.py keeps it boxed
            def lenv(nm, fp=fp, env=env):
                t = env(nm)
                if t in SCALAR:
                    return t
                return plan.lvar.get((fp.name, nm)) or t
            g = unified_lists.Gen(plan, fp, cons, lambda node, over=None, fp=fp, lenv=lenv: etype(
                plan, fp, node, lenv if not over else (lambda nm, over=over, lenv=lenv: over.get(nm) or lenv(nm))))
            g.run()
        uf = unified_lists.solve(cons, plan.float_guard)
        dbg = os.environ.get('AIL_UNIFIED_LISTS_DEBUG')
        if dbg and uf is not None:
            unified_lists.dump(uf, cons, dbg)
        new = {}
        tabs = {}
        elems = {}
        comps = {}
        ecomps = {}

        def ctypes(root):
            out = []
            for c in uf.comps[root]:
                cs = uf.st(c)
                out.append(cs[1] if isinstance(cs, tuple) else ('bot' if cs is None else 'obj'))
            return tuple(out)
        if uf is not None:
            for nk, k in plan.lkey.items():
                r = uf.find(k)
                s = uf.state[r]
                new[nk] = s[1] if isinstance(s, tuple) else (
                    'list' if s == unified_lists.L else
                    ('bot' if s is None else ('tuple' if unified_lists.is_p(s) else 'obj')))
                if s is None:
                    tabs[nk] = 'bot'
                    elems[nk] = 'bot'
                elif unified_lists.is_p(s):
                    comps[nk] = ctypes(r)
                elif s == unified_lists.L:
                    if uf.tab.get(r):
                        tabs[nk] = uf.tab[r]
                    er = uf.find(uf.elem[r])
                    es = uf.state[er]
                    elems[nk] = es[1] if isinstance(es, tuple) else ('bot' if es is None else 'obj')
                    if unified_lists.is_p(es):
                        ecomps[nk] = ctypes(er)
        lvar = {}
        if uf is not None:
            for k in uf.parent:
                if k[0] == 'v':
                    s = uf.st(k)
                    if isinstance(s, tuple):
                        lvar[(k[1], k[2])] = s[1]
        plan.lr_count = getattr(plan, 'lr_count', 0) + 1
        if plan.lr_count > 24:
            # two proofs that feed each other can take turns for ever (each is consistent on its own, Jacobi steps flip
            # between them): from here on a state only moves towards 'unknown', so the rounds settle
            new, elems = _damp(plan.lstate, new), _damp(plan.lelem, elems)
            comps, ecomps = _damp_t(plan.lcomps, comps), _damp_t(plan.lecomps, ecomps)
            lvar = {k: v for k, v in lvar.items() if plan.lvar.get(k) == v}
            tabs = {k: v for k, v in tabs.items() if plan.ltab.get(k, v) == v}
        if (new != plan.lstate or tabs != plan.ltab or elems != plan.lelem or lvar != plan.lvar
                or comps != plan.lcomps or ecomps != plan.lecomps) and os.environ.get('AIL_UNIFIED_ROUNDS_DEBUG') \
                and getattr(plan, 'dbg_round', 0) >= int(os.environ.get('AIL_UNIFIED_ROUNDS_FROM', '150')):
            with open(os.environ['AIL_UNIFIED_ROUNDS_DEBUG'], 'a') as _f:
                for nm, a_, b_ in (('lstate', plan.lstate, new), ('elems', plan.lelem, elems), ('lvar', plan.lvar, lvar),
                                   ('comps', plan.lcomps, comps), ('ecomps', plan.lecomps, ecomps)):
                    for k_ in set(a_) | set(b_):
                        if a_.get(k_) != b_.get(k_):
                            _f.write('  %s %s: %r -> %r' % (nm, k_[:2] if isinstance(k_, tuple) and k_ and isinstance(k_[0], str) else k_, a_.get(k_), b_.get(k_)) + chr(10))
        plan.dbg_round = getattr(plan, 'dbg_round', 0) + 1
        if new != plan.lstate or tabs != plan.ltab or elems != plan.lelem or lvar != plan.lvar \
                or comps != plan.lcomps or ecomps != plan.lecomps:
            plan.lstate = new
            plan.ltab = tabs
            plan.lelem = elems
            plan.lvar = lvar
            plan.lcomps = comps
            plan.lecomps = ecomps
            return True
        return False

    # ---- the fixed point
    def env_of(fp):
        return lambda nm: _name_type(plan, fp, nm)

    for _round in range(200):
        changed = lists_round()
        _rd = os.environ.get('AIL_UNIFIED_ROUNDS_DEBUG') if _round >= int(os.environ.get('AIL_UNIFIED_ROUNDS_FROM', '150')) else None
        if _rd and changed:
            with open(_rd, 'a') as _f:
                _f.write('round %d: lists changed' % _round + chr(10))
        for fp in plan.fns.values():
            env = env_of(fp)
            new = dict(fp.vtype)
            for i, p in enumerate(fp.params):
                if p in fp.locals:
                    new[p] = join(new[p], fp.ptypes[i] if fp.spec else OBJ)
            for n in fp.own_updates:
                if _pair_assign(n):
                    for tg, v in zip(n.targets[0].elts, n.value.elts):
                        if tg.id in new:
                            new[tg.id] = join(new[tg.id], etype(plan, fp, v, env))
                elif isinstance(n, ast.Assign):
                    t = etype(plan, fp, n.value, env)
                    for tg in n.targets:
                        if isinstance(tg, ast.Name) and tg.id in new:
                            new[tg.id] = join(new[tg.id], t)
                elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
                    if n.target.id in new:
                        new[n.target.id] = join(new[n.target.id], etype(plan, fp, n.value, env))
                elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id in new:
                    virt = ast.BinOp(left=ast.Name(id=n.target.id, ctx=ast.Load()), op=n.op, right=n.value)
                    new[n.target.id] = join(new[n.target.id], etype(plan, fp, virt, env))
                elif isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id in new \
                        and (_is_range_call(n.iter, names_all) or const_rows(plan, fp, n.iter, 1)):
                    new[n.target.id] = join(new[n.target.id], INT)
                elif isinstance(n, ast.For) and isinstance(n.target, ast.Tuple) \
                        and all(isinstance(e, ast.Name) for e in n.target.elts) \
                        and const_rows(plan, fp, n.iter, len(n.target.elts)) is not None:
                    for e in n.target.elts:
                        if e.id in new:
                            new[e.id] = join(new[e.id], INT)
                elif isinstance(n, ast.For) and isinstance(n.target, ast.Tuple) \
                        and all(isinstance(e, ast.Name) for e in n.target.elts) \
                        and len({e.id for e in n.target.elts}) == len(n.target.elts) \
                        and (tloop_types(plan, fp, n) is not None
                             or _is_zip(n.iter, len(n.target.elts), names_all)
                             or _is_enum(n.iter, len(n.target.elts), names_all)):
                    tp = tloop_types(plan, fp, n)
                    tp = tp[1] if tp is not None else None
                    for i, e in enumerate(n.target.elts):
                        if e.id not in new:
                            continue
                        tt = tp[i] if tp is not None else 'obj'
                        if tt in SCALAR:
                            new[e.id] = join(new[e.id], tt)
                        elif tt != 'bot':
                            new[e.id] = OBJ
                elif _unpackable(n):
                    tp = unpack_types(plan, fp, n)
                    for i, e in enumerate(n.targets[0].elts):
                        if e.id not in new:
                            continue
                        tt = tp[i] if tp is not None else 'obj'
                        if tt in SCALAR:
                            new[e.id] = join(new[e.id], tt)
                        elif tt != 'bot':
                            new[e.id] = OBJ
                elif isinstance(n, ast.For) and _local_iter(fp, n.iter) and 'bot' not in (
                        plan.ltab.get((fp.name, id(n.iter))), plan.lelem.get((fp.name, id(n.iter)))):
                    # a loop over a proven list of scalars binds a scalar; over anything else what it binds is boxed
                    el = plan.lelem.get((fp.name, id(n.iter)))
                    if isinstance(n.target, ast.Name) and el in SCALAR:
                        if n.target.id in new:
                            new[n.target.id] = join(new[n.target.id], el)
                    else:
                        for e in ([n.target] if isinstance(n.target, ast.Name) else n.target.elts
                                  if isinstance(n.target, ast.Tuple) else []):
                            if isinstance(e, ast.Name) and e.id in new:
                                new[e.id] = OBJ
            for v in fp.bad:
                if v in new:
                    new[v] = OBJ
            if new != fp.vtype:
                if _rd:
                    with open(_rd, 'a') as _f:
                        _f.write('round %d: %s: %s' % (_round, fp.name, {k: (fp.vtype[k], v) for k, v in new.items()
                                                                          if fp.vtype[k] != v}) + chr(10))
                fp.vtype = new
                changed = True
            if fp.spec:
                r = fp.ret
                if not _always_returns(fp.node.body):
                    r = join(r, OBJ)
                for n in fp.own_returns:
                    r = join(r, OBJ if n.value is None else etype(plan, fp, n.value, env))
                if r != fp.ret:
                    fp.ret = r
                    changed = True
        for name, sp in plan.spec.items():
            pt = list(sp.ptypes)
            for caller, call in sp.calls_in:
                if (caller.name, id(call)) in plan.generic_sites:
                    continue
                for i, a in enumerate(call.args):
                    t = etype(plan, caller, a, env_of(caller))
                    if t is not OBJ:
                        pt[i] = join(pt[i], t)       # a boxed argument sends its call to the boxed body
            if pt != sp.ptypes:
                sp.ptypes = pt
                changed = True
            for caller, call in sp.calls_in:
                key = (caller.name, id(call))
                if key in plan.generic_sites:
                    continue
                for i, a in enumerate(call.args):
                    t = etype(plan, caller, a, env_of(caller))
                    if pt[i] in SCALAR and t is not BOT and t != pt[i]:
                        plan.generic_sites.add(key)     # sticky: the result type of this call only rises
                        changed = True
                        break
        if not changed:
            # what is still bottom has no evidence (dead code, a function never called): widen it
            # parameters first (an annotation hint may give them a type), then the variables that depend on them
            widened = False
            for fp in plan.fns.values():
                if fp.spec:
                    for i, t in enumerate(fp.ptypes):
                        if t is BOT:
                            fp.ptypes[i] = fp.hints[i] if fp.hints[i] in SCALAR else OBJ
                            widened = True
            if widened:
                continue
            for fp in plan.fns.values():
                for v, t in fp.vtype.items():
                    if t is BOT:
                        fp.vtype[v] = OBJ
                        widened = True
                if fp.spec and fp.ret is BOT:
                    fp.ret = OBJ
                    widened = True
            if not widened:
                break
    else:
        raise Conflict(('<module>', '*'), 'the type analysis did not settle')
    # a specialisation that changes nothing, or that no call reaches with its types, is dropped
    for name in list(plan.spec):
        sp = plan.spec[name]
        if sp.ret not in SCALAR and not any(t in SCALAR for t in sp.ptypes):
            del plan.spec[name]
            del plan.fns[sp.name]
    # the boxed body of a specialised function is emitted only when something can reach it: a call from
    # code this pass does not analyse, the function used as a value, or a call whose arguments do not match
    # (from any body that is itself emitted). Otherwise the specialised body is the only one (binary size).
    calls_by_owner = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in plan.spec:
            if id(n) not in owner:
                plan.need_generic.add(n.func.id)
    callee_names = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in plan.spec and id(n) not in callee_names:
            plan.need_generic.add(n.id)
    generic_of = {sp.info['cname']: name for name, sp in plan.spec.items()}
    bodies = [fp for fp in plan.fns.values() if fp.name not in generic_of]
    bodies += [plan.fns[sp.info['cname']] for name, sp in plan.spec.items()
               if name in plan.need_generic and sp.info['cname'] in plan.fns]
    seen = set()
    while bodies:
        fp = bodies.pop()
        if fp.name in seen:
            continue
        seen.add(fp.name)
        for n in fp.own:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in plan.spec:
                if not site_matches(plan, fp, n) and n.func.id not in plan.need_generic:
                    plan.need_generic.add(n.func.id)
                    g = plan.fns.get(plan.spec[n.func.id].info['cname'])
                    if g is not None:
                        bodies.append(g)
    # a library function the compiler added (json, re, ...) is not worth two bodies: when its boxed body
    # must stay, it is not specialised at all (its locals are still unboxed)
    twice = {('pfu_' + name, '*') for name in plan.need_generic if name.startswith('_ail')}
    if twice - demote:
        return analyze(comp, tree, demote | twice, nofloat)
    risk = None if nofloat or not _has_float(plan) else float_search_risk(plan, tree, comp)
    narrow_site = None
    if risk:
        # first the narrow form: only the float locals that may be boxed twice are kept boxed; a loop of plain
        # float arithmetic stays unboxed. When the proof does not apply (floats inside typed lists), every float
        narrow = float_escape_demotes(plan, tree, comp)
        if narrow is not None and narrow - demote:
            return analyze(comp, tree, demote | narrow, nofloat)
        elif narrow is not None:
            narrow_site, risk = risk, None        # no float local can be boxed twice any more
    if risk:
        # C118: a NaN the scan of `nan_capable` cannot see (made by arithmetic on an overflow, parsed from data)
        # would lose its identity at the next box, and the program searches a container with a value that may be
        # a float: no float is unboxed in this program (they keep the general path's one box per value)
        again = analyze(comp, tree, demote, True)
        again.stats['floats_kept_boxed'] = risk
        return again
    plan.stats = {
        'functions': len(plan.fns),
        'generic_bodies_kept': sorted(plan.need_generic),
        'unboxed_vars': sum(1 for fp in plan.fns.values() for v in fp.locals if fp.unboxed(v)),
        'boxed_vars': sum(1 for fp in plan.fns.values() for v in fp.locals if not fp.unboxed(v)),
        'specialised': sorted(plan.spec),
        'constants': sorted(plan.gconst),
        'closed': sorted(plan.closed),
        'typed_elements': sum(1 for v in plan.lstate.values() if v in SCALAR),
        'tables': sorted(plan.ctables),
        'local_tables': sum(1 for v in plan.ltab.values() if v != 'bot'),
        'draws': sorted(plan.draws),
        'floats_kept_boxed': False,
        'float_search_site': narrow_site,
        'float_locals_kept_boxed': sorted('%s:%s' % kv for kv in demote if kv[0] != '<module>'),
    }
    return plan


def _identity_leaves(e, out):
    """The names whose object an expression may hand back unchanged: the leaves a value reaches
    through `and` / `or`, `a if c else b`, `(n := v)` and a call argument."""
    if isinstance(e, ast.Name):
        out.add(e.id)
    elif isinstance(e, ast.BoolOp):
        for v in e.values:
            _identity_leaves(v, out)
    elif isinstance(e, ast.IfExp):
        _identity_leaves(e.body, out)
        _identity_leaves(e.orelse, out)
    elif isinstance(e, ast.NamedExpr):
        _identity_leaves(e.target, out)
        _identity_leaves(e.value, out)
    elif isinstance(e, ast.Call):
        for a in e.args:
            _identity_leaves(a.value if isinstance(a, ast.Starred) else a, out)
        for k in e.keywords:
            _identity_leaves(k.value, out)


def _identity_free(e):
    """`is` against this side cannot see a fresh box as different: None, True, False, a str or bytes."""
    return isinstance(e, ast.Constant) and (e.value is None or isinstance(e.value, (bool, str, bytes)))


def _identity_compares(nodes):
    for n in nodes:
        if isinstance(n, ast.Compare) and any(isinstance(o, (ast.Is, ast.IsNot)) for o in n.ops):
            sides = [n.left] + list(n.comparators)
            for i, o in enumerate(n.ops):
                if isinstance(o, (ast.Is, ast.IsNot)):
                    a, b = sides[i], sides[i + 1]
                    if not (_identity_free(a) or _identity_free(b)):
                        yield a, b


def _identity_names(own):
    """C101: `is` / `is not` compares objects, and an unboxed number has none: the locals that an
    `is` may compare with another object stay boxed (a float is a heap object; the same name read
    twice must be the same box)."""
    out = set()
    for a, b in _identity_compares(own):
        _identity_leaves(a, out)
        _identity_leaves(b, out)
    return out


def _identity_callees(tree, functions):
    """The functions called in an `is` operand: their result may be one of their arguments."""
    out = set()
    for a, b in _identity_compares(ast.walk(tree)):
        for e in (a, b):
            for x in ast.walk(e):
                if isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id in functions:
                    out.add(x.func.id)
    return out


def _int_const(e):
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.USub) and isinstance(e.operand, ast.Constant):
        v = e.operand.value
        if isinstance(v, int) and not isinstance(v, bool) and _I64_MIN <= -v <= _I64_MAX:
            return -v
        return None
    if isinstance(e, ast.Constant) and isinstance(e.value, int) and not isinstance(e.value, bool) \
            and _I64_MIN <= e.value <= _I64_MAX:
        return e.value
    return None


def _table_rows(elts):
    """The rows of a table of int constants (k = 1: the ints themselves) as (k, [[int]]), or None."""
    if not elts:
        return None
    if all(_int_const(e) is not None for e in elts):
        return 1, [[_int_const(e)] for e in elts]
    if all(isinstance(e, ast.Tuple) for e in elts):
        k = len(elts[0].elts)
        rows = []
        for e in elts:
            if len(e.elts) != k or k < 2:
                return None
            row = [_int_const(x) for x in e.elts]
            if any(v is None for v in row):
                return None
            rows.append(row)
        return k, rows
    return None


def const_rows(plan, fp, it, k):
    """The rows of `for ... in it` when it is a display of int constants (or a module table) with rows of k."""
    if isinstance(it, ast.Name):
        if fp is not None and it.id in fp.locals:
            # a local list proven to hold one constant display, never changed (unified_lists.py: tab)
            rows = getattr(plan, 'ltab', {}).get((fp.name, id(it)))
            if rows == 'bot' or not rows:
                return None
            return [list(r) for r in rows] if len(rows[0]) == k else None
        elts = plan.ctables.get(it.id)
    elif isinstance(it, (ast.Tuple, ast.List)) and isinstance(it.ctx, ast.Load):
        elts = it.elts
    else:
        return None
    if elts is None:
        return None
    tr = _table_rows(elts)
    if tr is None or tr[0] != k:
        return None
    return tr[1]


def rows_any(plan, fp, it):
    """The rows (any width) of a table `it` (display, module table or proven local table), 'bot' while the
    local's class is not known yet, else None."""
    if isinstance(it, ast.Name) and fp is not None and it.id in fp.locals:
        rows = plan.ltab.get((fp.name, id(it)))
        return rows if rows == 'bot' else ([list(r) for r in rows] if rows else None)
    for k in range(1, 9):
        rows = const_rows(plan, fp, it, k)
        if rows:
            return rows
    return None


def _row_read(plan, fp, n):
    """`r[c]` of a row variable (see analyze) over a table of rows of width >= 2: (rows, column), 'bot', or None."""
    if not (fp is not None and isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load)
            and isinstance(n.value, ast.Name) and n.value.id in getattr(fp, 'rowvars', {})):
        return None
    c = _int_const(n.slice)
    rows = rows_any(plan, fp, fp.rowvars[n.value.id].iter)
    if rows == 'bot':
        return 'bot'
    if not rows or c is None or len(rows[0]) < 2 or not -len(rows[0]) <= c < len(rows[0]):
        return None
    return rows, c % len(rows[0])


def _pair_assign(s):
    """`a, b = x, y`: one tuple target of names, a tuple display of the same length, nothing starred."""
    if not (isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Tuple)
            and isinstance(s.value, ast.Tuple)):
        return False
    t, v = s.targets[0], s.value
    return (len(t.elts) == len(v.elts) and all(isinstance(e, ast.Name) for e in t.elts)
            and not any(isinstance(e, ast.Starred) for e in v.elts)
            and len({e.id for e in t.elts}) == len(t.elts))


def _damp1(old, new):
    if old is None or old == new:
        return new
    if new == 'bot':
        return old
    if old == 'bot':
        return new
    return 'obj'


def _damp(old, new):
    """The states of `new`, but where a state of `old` differs the unknown one ('obj')."""
    return {k: _damp1(old.get(k), v) for k, v in new.items()}


def _damp_t(old, new):
    out = {}
    for k, v in new.items():
        o = old.get(k)
        out[k] = v if o is None or len(o) != len(v) else tuple(_damp1(a, b) for a, b in zip(o, v))
    return out


def _is_zip(it, k, fn_names):
    """Syntactically `zip(a, b, ...)` with k positional arguments (the builtin is checked by tloop_types)."""
    return (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'zip'
            and 'zip' not in fn_names and not it.keywords and len(it.args) == k and k >= 2
            and not any(isinstance(a, ast.Starred) for a in it.args))


def _is_enum(it, k, fn_names):
    """Syntactically `enumerate(xs)` / `enumerate(xs, <int constant>)` as the iterable of a two-name loop."""
    if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'enumerate'
            and 'enumerate' not in fn_names and not it.keywords and k == 2
            and not any(isinstance(a, ast.Starred) for a in it.args)):
        return False
    if len(it.args) == 1:
        return True
    return (len(it.args) == 2 and isinstance(it.args[1], ast.Constant) and type(it.args[1].value) is int
            and -(1 << 62) < it.args[1].value < (1 << 62))


def tloop_types(plan, fp, node):
    """`for a, b in <iterable>` (distinct names): ('zip' | 'enum' | 'vec', the proven type of each name: 'int' /
    'float' / 'bool' / 'obj' / 'bot'), when the loop is one this pass lowers (zip or enumerate of proven lists, or a
    proven list of proven tuples); else None. Used by the type analysis and by the code generation, which must
    agree."""
    tg = node.target
    if not (isinstance(tg, ast.Tuple) and all(isinstance(e, ast.Name) for e in tg.elts)):
        return None
    k = len(tg.elts)
    it = node.iter
    if _is_zip(it, k, plan.fn_names) and _builtin(plan, fp, 'zip'):
        out = []
        for a in it.args:
            key = (fp.name, id(a))
            st = plan.lstate.get(key)
            if st == 'bot':
                out.append('bot')
            elif st == 'list':
                out.append(plan.lelem.get(key))
            else:
                return None
        return ('zip', out)
    if _is_enum(it, k, plan.fn_names) and _builtin(plan, fp, 'enumerate'):
        key = (fp.name, id(it.args[0]))
        st = plan.lstate.get(key)
        if st == 'bot':
            return ('enum', ['int', 'bot'])
        if st == 'list':
            return ('enum', ['int', plan.lelem.get(key)])
        return None
    if _local_iter(fp, it) and not const_rows(plan, fp, it, k):
        key = (fp.name, id(it))
        st = plan.lstate.get(key)
        if st == 'list' and plan.lelem.get(key) == 'obj' and plan.ltab.get(key) is None:
            c = plan.lecomps.get(key)
            if c is not None and len(c) == k:
                return ('vec', list(c))
    return None


def unpack_types(plan, fp, node):
    """`a, b = value` (an assignment of one value to a tuple of distinct names, not `a, b = x, y`): the proven type of
    each name when the value is proven a tuple of that many components, else None."""
    tg = node.targets[0]
    key = (fp.name, id(node.value))
    st = plan.lstate.get(key)
    if st == 'bot':
        return ['bot'] * len(tg.elts)
    if st == 'tuple':
        c = plan.lcomps.get(key)
        if c is not None and len(c) == len(tg.elts):
            return list(c)
    return None


def _unpackable(node):
    return (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple)
            and len(node.targets[0].elts) >= 2 and all(isinstance(e, ast.Name) for e in node.targets[0].elts)
            and len({e.id for e in node.targets[0].elts}) == len(node.targets[0].elts)
            and not _pair_assign(node))


def _local_iter(fp, it):
    """The iterable of a for loop that unified_lists.py may prove a list: a local, or an element read xs[i]."""
    return ((isinstance(it, ast.Name) and it.id in fp.locals)
            or (isinstance(it, ast.Subscript) and isinstance(it.ctx, ast.Load)
                and not isinstance(it.slice, ast.Slice)))


def _ann_type(a):
    if isinstance(a, ast.Name):
        return {'int': INT, 'float': FLOAT, 'bool': BOOL}.get(a.id, OBJ)
    if isinstance(a, ast.Constant) and isinstance(a.value, str):
        return {'int': INT, 'float': FLOAT, 'bool': BOOL}.get(a.value, OBJ)
    return OBJ


# ---- the draws of random.Random (prelude_random_boxed.py, in C in randrt.py). Each of these methods returns one type
# whenever it returns: random/expovariate/uniform/gauss a float, randrange/randint/getrandbits an int. On the general
# path a call `r.m(...)` of a method that only class Random defines either runs Random's method (the receiver is a
# Random or a subclass that does not override it) or raises AttributeError, so its value has that type wherever the
# receiver came from: a local, a parameter, `self.rng`, the module's `_ail_rng` (what `random.random()` becomes).
_DRAWS = {
    'random': (FLOAT, (0,)),
    'expovariate': (FLOAT, (1,)),
    'uniform': (FLOAT, (2,)),
    'gauss': (FLOAT, (0, 1, 2)),
    'randrange': (INT, (1, 2, 3)),
    'randint': (INT, (2,)),
    'getrandbits': (INT, (1,)),
    'choice': (None, (1,)),             # an element of its argument: an int for a display of int constants
}
_PRELUDE_RANDOM = None


def _native_draws(comp):
    """method name -> (result type, arities) for the draws this program can take unboxed: the class Random of the
    program is prelude_random_boxed.py's (method by method, as written there), no other class defines a method of
    that name, and no built-in method of that name exists on the general path."""
    global _PRELUDE_RANDOM
    cls = comp.classes.get('Random')
    if cls is None:
        return {}
    if _PRELUDE_RANDOM is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prelude_random_boxed.py')
        with open(path, 'r', encoding='utf-8') as handle:
            body = ast.parse(handle.read()).body[0].body
        _PRELUDE_RANDOM = {m.name: ast.dump(m) for m in body if isinstance(m, ast.FunctionDef)}
    if cls.get('base') is not None:
        return {}
    out = {}
    for m, spec in _DRAWS.items():
        info = cls['methods'].get(m)
        if info is None or _PRELUDE_RANDOM.get(m) is None or ast.dump(info['node']) != _PRELUDE_RANDOM[m]:
            continue
        if any(m in comp.classes[c]['methods'] for c in comp.classes if c != 'Random'):
            continue
        if getattr(comp, '_m_' + m, None) is not None:
            continue
        if any(str(k).endswith('.' + m) for k in getattr(comp, 'names_methods', {}) or {}):
            continue
        out[m] = spec
    return out


def _draw_of(plan, n):
    """The (method, result type) of a draw call `r.m(...)` this pass types, or None."""
    if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in plan.draws):
        return None
    if n.keywords or any(isinstance(a, ast.Starred) for a in n.args):
        return None
    t, arities = plan.draws[n.func.attr]
    if len(n.args) not in arities:
        return None
    r = n.func.value
    if isinstance(r, ast.Name) and r.id in plan.not_receivers:
        return None
    if isinstance(r, ast.Call) and isinstance(r.func, ast.Name) and r.func.id == 'super':
        return None
    if t is None:       # choice(seq)
        a = n.args[0]
        if not (isinstance(a, (ast.Tuple, ast.List)) and a.elts and all(_int_const(e) is not None for e in a.elts)):
            return None
        t = INT
    return n.func.attr, t


def site_matches(plan, fp, call):
    """Whether the call `call` (to a specialised function) in function plan `fp` goes to the unboxed body."""
    sp = plan.spec[call.func.id]
    if call.keywords or len(call.args) != len(sp.params) or any(isinstance(a, ast.Starred) for a in call.args):
        return False
    if fp is None:
        return not any(t in SCALAR for t in sp.ptypes)
    if (fp.name, id(call)) in plan.generic_sites:
        return False
    env = lambda nm: _name_type(plan, fp, nm)
    return all(t not in SCALAR or etype(plan, fp, a, env) == t for a, t in zip(call.args, sp.ptypes))


def _name_type(plan, fp, nm):
    if nm in fp.locals:
        t = fp.vtype.get(nm)
        return OBJ if nm in fp.bad else t
    if nm in plan.gconst:
        return plan.gconst[nm]
    return OBJ


_ARITH = (ast.Add, ast.Sub, ast.Mult)
_BITS = (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift)
_ORDER = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)


def _builtin(plan, fp, name):
    """`name` called here is the builtin (not a local, a module name or a function of the program)."""
    return ((fp is None or name not in fp.locals) and name not in plan.module_names
            and name not in plan.fn_names)


def etype(plan, fp, n, env):
    """The lattice value of expression `n` in function `fp`, under the variable types `env`.
    A scalar answer means the emitter can produce the value unboxed (`Emit.nexpr`)."""
    t = _etype(plan, fp, n, env)
    return OBJ if (t == FLOAT and plan.nofloat) else t


def _etype(plan, fp, n, env):
    if isinstance(n, ast.Constant):
        v = n.value
        if isinstance(v, bool):
            return BOOL
        if isinstance(v, int):
            return INT if _I64_MIN <= v <= _I64_MAX else OBJ
        if isinstance(v, float):
            return FLOAT
        return OBJ
    if isinstance(n, ast.Name):
        return env(n.id)
    if isinstance(n, ast.BinOp):
        a, b = etype(plan, fp, n.left, env), etype(plan, fp, n.right, env)
        if a is BOT or b is BOT:
            return BOT if OBJ not in (a, b) else OBJ
        op = n.op
        if a == INT and b == INT:
            if isinstance(op, _ARITH + _BITS + (ast.FloorDiv, ast.Mod)):
                return INT
            if isinstance(op, ast.Div):
                return FLOAT
            return OBJ
        if a in (INT, FLOAT) and b in (INT, FLOAT):
            if isinstance(op, _ARITH + (ast.Div, ast.FloorDiv, ast.Mod)):
                return FLOAT
            return OBJ
        return OBJ
    if isinstance(n, ast.UnaryOp):
        if isinstance(n.op, ast.Not):
            return BOOL
        a = etype(plan, fp, n.operand, env)
        if a is BOT:
            return BOT
        if isinstance(n.op, (ast.USub, ast.UAdd)) and a in (INT, FLOAT):
            return a
        if isinstance(n.op, ast.Invert) and a == INT:
            return INT
        return OBJ
    if isinstance(n, ast.Compare):
        if any(isinstance(o, (ast.In, ast.NotIn, ast.Is, ast.IsNot)) for o in n.ops):
            if len(n.ops) == 1:
                return BOOL           # `in` and `is` always give a bool
            return OBJ
        ts = [etype(plan, fp, x, env) for x in [n.left] + n.comparators]
        if any(t is BOT for t in ts) and OBJ not in ts:
            return BOT
        if all(t in (INT, FLOAT, BOOL) for t in ts):
            # bool compares as an int; the result of a numeric comparison is a bool
            return BOOL
        return OBJ
    if isinstance(n, ast.BoolOp):
        ts = [etype(plan, fp, x, env) for x in n.values]
        if any(t is BOT for t in ts) and OBJ not in ts:
            return BOT
        return BOOL if all(t == BOOL for t in ts) else OBJ
    if isinstance(n, ast.IfExp):
        a, b = etype(plan, fp, n.body, env), etype(plan, fp, n.orelse, env)
        return join(a, b)
    d = _draw_of(plan, n)
    if d is not None:
        return d[1]
    rr = _row_read(plan, fp, n)
    if rr is not None:
        return BOT if rr == 'bot' else INT
    if isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load) and not isinstance(n.slice, ast.Slice) \
            and fp is not None:
        s = plan.lstate.get((fp.name, id(n)))
        if s in SCALAR:
            return s
        return BOT if s == 'bot' else OBJ
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and not n.keywords \
            and not any(isinstance(a, ast.Starred) for a in n.args):
        f = n.func.id
        if f in plan.spec:
            sp = plan.spec[f]
            if (fp is None or (fp.name, id(n)) in plan.generic_sites or len(n.args) != len(sp.params)):
                return OBJ
            return sp.ret
        if not _builtin(plan, fp, f):
            return OBJ
        k = len(n.args)
        if f in ('len', 'ord') and k == 1:
            return INT
        if f == 'int' and k in (1, 2):
            return INT
        if f == 'float' and k == 1:
            return FLOAT
        if f in ('bool', 'isinstance', 'callable') and k in ((1,) if f != 'isinstance' else (2,)):
            return BOOL
        if f == 'round' and k == 1:
            a = etype(plan, fp, n.args[0], env)
            return INT if a in (INT, FLOAT) else (BOT if a is BOT else OBJ)
        if f == 'abs' and k == 1:
            a = etype(plan, fp, n.args[0], env)
            return a if a in (INT, FLOAT, BOT) else OBJ
        if f in ('min', 'max') and k >= 2:
            ts = [etype(plan, fp, x, env) for x in n.args]
            if any(t is BOT for t in ts) and OBJ not in ts:
                return BOT
            if all(t == INT for t in ts):
                return INT
            if all(t == FLOAT for t in ts):
                return FLOAT
        return OBJ
    return OBJ


# ============================================================================== emission
#
# Hooks called by pyboxed2 when `comp.uplan` is set (AIL_UNIFIED=1). `ctx.u` is the FnPlan of the
# function being emitted (None for module code, lambdas, nested functions and functions this pass
# left alone). Every native value is a C local (`u_<name>` for a variable, `_u<n>` for a
# temporary) declared at the top of the function, so no jump of the general path's error edges
# crosses a declaration.

_CMP_C = {ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>=', ast.Eq: '==', ast.NotEq: '!='}
_CMP_RT = {ast.Lt: 'ail_op_lt', ast.LtE: 'ail_op_le', ast.Gt: 'ail_op_gt', ast.GtE: 'ail_op_ge',
           ast.Eq: 'ail_op_eq', ast.NotEq: 'ail_op_ne'}
_BIN_RT = {ast.Add: 'ail_op_add', ast.Sub: 'ail_op_sub', ast.Mult: 'ail_op_mul', ast.Div: 'ail_op_truediv',
           ast.FloorDiv: 'ail_op_floordiv', ast.Mod: 'ail_op_mod', ast.BitAnd: 'ail_op_bitand',
           ast.BitOr: 'ail_op_bitor', ast.BitXor: 'ail_op_bitxor', ast.LShift: 'ail_op_lshift',
           ast.RShift: 'ail_op_rshift'}
_OVF = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul'}


def begin_function(comp, info, ctx):
    """Attach the plan of the function to its emission context; the C declarations of its native locals."""
    plan = comp.uplan
    fp = plan.fns.get(info['cname']) if plan is not None else None
    ctx.u = fp
    ctx.u_decls = []
    ctx.u_n = 0
    if fp is None:
        return
    for v in sorted(fp.locals):
        if fp.unboxed(v):
            ctx.u_decls.append('%s %s = 0;' % (CTYPE[fp.vtype[v]], fp.cvar(v)))
            ctx.var_kind[v] = KIND[fp.vtype[v]]


def _spec_of(plan, info):
    if plan is None or info.get('is_method'):
        return None
    sp = plan.spec.get(info['node'].name)
    return sp if sp is not None and sp.info is not None and sp.info['node'] is info['node'] else None


def signature(plan, info):
    """(C name, parameter list after `ail_ctx *cx`) of the specialised body of the function, or None."""
    sp = _spec_of(plan, info)
    if sp is None:
        return None
    out = '%s *out' % (CTYPE[sp.ret] if sp.ret in SCALAR else 'ail_obj')
    ps = ''.join(', %s pv_%s' % (CTYPE[t] if t in SCALAR else 'ail_obj', p) for p, t in zip(sp.params, sp.ptypes))
    return sp.name, out + ps


def entry_guard(plan, info):
    """The first lines of the boxed body of a specialised function: arguments that carry the specialised
    types go to the unboxed body."""
    sp = _spec_of(plan, info)
    if sp is None or info['cname'] == sp.name:
        return ''
    tag = {INT: 'AIL_T_INT', FLOAT: 'AIL_T_FLOAT', BOOL: 'AIL_T_BOOL'}
    conds, args = [], []
    for p, t in zip(sp.params, sp.ptypes):
        if t in SCALAR:
            conds.append('pv_%s.tag == %s' % (p, tag[t]))
            args.append('ail_float_val(pv_%s)' % p if t == FLOAT else ('pv_%s.i' % p))
        else:
            args.append('pv_' + p)
    call = '%s(cx, %%s%s)' % (sp.name, ''.join(', ' + a for a in args))
    if sp.ret in SCALAR:
        body = ('        %s _ur; ail_st _st = %s;\n'
                '        if (_st == AIL_OK) *out = %s;\n'
                '        return _st;\n') % (CTYPE[sp.ret], call % '&_ur', _box_rv(sp.ret, '_ur'))
    else:
        body = '        return %s;\n' % (call % 'out')
    return '    if (%s) {\n%s    }\n' % (' && '.join(conds) or '1', body)


def param_preamble(comp, info, ctx):
    """The lines that move the C parameters into their storage, or None for the general path's own."""
    fp = ctx.u
    if fp is None:
        return None
    lines = []
    for i, p in enumerate(info['all_params']):
        pt = fp.ptypes[i] if fp.spec and i < len(fp.ptypes) else OBJ
        if fp.unboxed(p):
            if pt != fp.vtype[p]:
                raise Conflict((fp.name, p), 'parameter type %s, variable %s' % (pt, fp.vtype[p]))
            lines.append('    %s = pv_%s;' % (fp.cvar(p), p))
        elif pt in SCALAR:
            lines.append('    f.slots[%d] = %s;' % (ctx.slot_of[p], _box_rv(pt, 'pv_' + p)))
        else:
            lines.append('    f.slots[%d] = pv_%s;' % (ctx.slot_of[p], p))
    return lines


def _box_rv(t, v):
    return {INT: 'ail_box_int(%s)', BOOL: 'ail_box_bool(%s)', FLOAT: 'ail_box_float(cx, %s)'}[t] % v


def ntype(comp, ctx, node):
    fp = ctx.u
    plan = comp.uplan
    return etype(plan, fp, node, lambda nm: _name_type(plan, fp, nm))


def utmp(ctx, t):
    ctx.u_n += 1
    name = '_u%d' % ctx.u_n
    ctx.u_decls.append('%s %s = 0;' % (CTYPE[t], name))
    return name


def box(comp, ctx, v, t):
    if t != FLOAT:
        # an int or bool box is a value with no heap part: no slot, no store (the general path's own
        # True/False are such rvalues too); a float box is a heap object and is rooted in a slot
        return _box_rv(t, v)
    s = ctx.tmp()
    ctx.emit('%s = %s;' % (s, _box_rv(t, v)))
    return s


def _unbox_rv(s, t):
    if t == FLOAT:
        return '((%s).tag == AIL_T_FLOAT ? ail_float_val(%s) : (double)(%s).i)' % (s, s, s)
    if t == BOOL:
        return '((%s).i != 0)' % s
    return '(%s).i' % s


def unbox(ctx, s, t):
    r = utmp(ctx, t)
    ctx.emit('%s = %s;' % (r, _unbox_rv(s, t)))
    return r


def _c_const(v):
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, int):
        return '(-9223372036854775807LL - 1)' if v == _I64_MIN else '(%dLL)' % v
    if v != v:
        return '__builtin_nan("")'
    if v in (float('inf'), float('-inf')):
        return '__builtin_inf()' if v > 0 else '(-__builtin_inf())'
    return '(%s)' % float.hex(v)


def _natively_computed(comp, ctx, node):
    """Whether emitting `node` unboxed and boxing the result beats the general path's own code."""
    fp = ctx.u
    if isinstance(node, ast.Name):
        return node.id in fp.locals and fp.unboxed(node.id)
    if isinstance(node, (ast.BinOp, ast.BoolOp, ast.IfExp)):
        return True
    if isinstance(node, ast.UnaryOp):
        return not isinstance(node.op, ast.Not) or ntype(comp, ctx, node.operand) in SCALAR
    if isinstance(node, ast.Compare):
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)) \
                and isinstance(node.comparators[0], (ast.Tuple, ast.List)) and node.comparators[0].elts \
                and all(_int_const(e) is not None for e in node.comparators[0].elts):
            return ntype(comp, ctx, node.left) == INT
        return not any(isinstance(o, (ast.In, ast.NotIn, ast.Is, ast.IsNot)) for o in node.ops)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        f = node.func.id
        return f in comp.uplan.spec or (f in ('min', 'max') and _builtin(comp.uplan, fp, f))
    d = _draw_of(comp.uplan, node)
    if d is not None:
        return d[0] != 'choice'
    if isinstance(node, ast.Subscript) and _row_read(comp.uplan, fp, node) not in (None, 'bot'):
        return True
    return False


def expr_hook(comp, node, ctx):
    """pyboxed2.expr: the boxed value of a proven expression computed unboxed, or None."""
    fp = getattr(ctx, 'u', None)
    if fp is None or isinstance(node, ast.Constant):
        return None
    plan = comp.uplan
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in plan.spec
            and site_matches(plan, fp, node)):
        v, t = call_spec(comp, node.func.id, node.args, ctx)
        return box(comp, ctx, v, t) if t in SCALAR else v
    if list_read(comp, ctx, node):
        return _subscript(comp, node, ctx, None)
    pal = _palindrome_test(comp, ctx, node)
    if pal is not None:
        return _palindrome(comp, ctx, node, pal)
    if _bytearray_read(comp, ctx, node):
        return _bytearray_subscript(comp, node, ctx)
    t = ntype(comp, ctx, node)
    if t not in SCALAR or not _natively_computed(comp, ctx, node):
        return None
    return box(comp, ctx, nexpr(comp, node, ctx), t)


def _palindrome_test(comp, ctx, node):
    """`s == s[::-1]` / `s != s[::-1]` (either order) with `s` a name: (the name, negated), else None."""
    if not (isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq))):
        return None
    if os.environ.get('AIL_UNIFIED_STR') == '0' or '_ail' in ctx.u.name:
        return None
    a, b = node.left, node.comparators[0]
    for nm, sl in ((a, b), (b, a)):
        if (isinstance(nm, ast.Name) and isinstance(sl, ast.Subscript) and isinstance(sl.value, ast.Name)
                and sl.value.id == nm.id and isinstance(sl.ctx, ast.Load) and isinstance(sl.slice, ast.Slice)
                and sl.slice.lower is None and sl.slice.upper is None and sl.slice.step is not None
                and isinstance(sl.slice.step, ast.UnaryOp) and isinstance(sl.slice.step.op, ast.USub)
                and isinstance(sl.slice.step.operand, ast.Constant) and sl.slice.step.operand.value == 1
                and type(sl.slice.step.operand.value) is int):
            return nm, isinstance(node.ops[0], ast.NotEq)
    return None


def _palindrome(comp, ctx, node, pal):
    """A str compared with its own reversal is read in place: no reversed copy is built. Anything that is not a
    str is the general path's own code for the whole comparison (a list, a tuple, bytes, an error)."""
    nm, neg = pal
    cv = ctx.tmp()
    ctx.emit('%s = %s;' % (cv, comp.expr(nm, ctx)))
    r = ctx.tmp()
    comp.rt_needs.add('str_u')
    _open(ctx, 'if (%s.tag == AIL_T_STR) {' % cv)
    ctx.emit('%s = ail_box_bool(%sail2u_palindrome(%s));' % (r, '!' if neg else '', cv))
    ctx.indent -= 1
    ctx.emit('} else {')
    ctx.indent += 1
    ctx.emit('%s = %s;' % (r, comp._expr_plain(node, ctx)))
    _close(ctx)
    return r


def _err(ctx):
    ctx.uses_st = True
    return ctx.cur_err_target()


def _slot_of(comp, ctx, v, t):
    """A boxed copy of native `v` in a frame slot (a float box must be rooted while a runtime call allocates)."""
    return box(comp, ctx, v, t)


def _fallback(comp, ctx, fn, operands, rtype, r):
    """Run the general path's own operation on boxed operands (the rare edge: overflow, a zero divisor,
    a shift out of range) and unbox its result into `r`."""
    # three scratch slots per function, shared by every fallback: each is dead once its result is unboxed
    if not getattr(ctx, 'u_scratch', None):
        ctx.u_scratch = [ctx.tmp() for _ in range(3)]
    boxed = []
    for (v, t), s in zip(operands, ctx.u_scratch):
        ctx.emit('%s = %s;' % (s, _box_rv(t, v)))
        boxed.append(s)
    out = ctx.u_scratch[2]
    ctx.emit('st = %s(cx, &%s%s);' % (fn, out, ''.join(', ' + b for b in boxed)))
    ctx.emit('if (st != AIL_OK) goto %s;' % _err(ctx))
    ctx.emit('%s = %s;' % (r, _unbox_rv(out, rtype)))


def _open(ctx, line):
    ctx.emit(line)
    ctx.indent += 1


def _close(ctx, line='}'):
    ctx.indent -= 1
    ctx.emit(line)


def ntest(comp, node, ctx):
    t = ntype(comp, ctx, node)
    v = nexpr(comp, node, ctx)
    if t == BOOL:
        return v
    if t == INT:
        return '(%s != 0)' % v
    return '(%s != 0.0)' % v


def _f(v, t):
    return '((double)%s)' % v if t != FLOAT else v


def nexpr(comp, node, ctx):
    """The C value (a constant or a C local) of proven expression `node`; its statements are emitted."""
    fp = ctx.u
    t = ntype(comp, ctx, node)
    if t not in SCALAR:
        raise Conflict((fp.name, '*'), 'unboxed value of a boxed expression %s' % ast.dump(node)[:80])
    if isinstance(node, (ast.BinOp, ast.UnaryOp)):
        folded = pyfunc.fold_int_constant(node)
        if folded is not None:
            return _c_const(folded)
    if isinstance(node, ast.Constant):
        return _c_const(node.value)
    if isinstance(node, ast.Name):
        if node.id in fp.locals:
            return fp.cvar(node.id)
        g = comp.name_ref(node.id, ctx)
        ctx.emit('if ((%s).tag == AIL_T_UNBOUND) { st = ail_raise_c(cx, AIL_B_NAMEERROR, '
                 '"name \'%s\' is not defined"); goto %s; }' % (g, node.id, _err(ctx)))
        return unbox(ctx, g, t)
    if isinstance(node, ast.BinOp):
        return _binop(comp, node, ctx, t)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            if ntype(comp, ctx, node.operand) in SCALAR:
                r = utmp(ctx, BOOL)
                ctx.emit('%s = !%s;' % (r, ntest(comp, node.operand, ctx)))
                return r
            return unbox(ctx, comp._expr_plain(node, ctx), BOOL)
        a = nexpr(comp, node.operand, ctx)
        if isinstance(node.op, ast.UAdd):
            return a
        r = utmp(ctx, t)
        if isinstance(node.op, ast.Invert):
            ctx.emit('%s = ~%s;' % (r, a))
        elif t == FLOAT:
            ctx.emit('%s = -%s;' % (r, a))
        else:
            _open(ctx, 'if (%s == INT64_MIN) {' % a)
            _fallback(comp, ctx, 'ail_op_neg', [(a, INT)], INT, r)
            _close(ctx, '} else {')
            ctx.indent += 1
            ctx.emit('%s = -%s;' % (r, a))
            _close(ctx)
        return r
    if isinstance(node, ast.Compare):
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)) \
                and ntype(comp, ctx, node.left) == INT and isinstance(node.comparators[0], (ast.Tuple, ast.List)) \
                and node.comparators[0].elts and all(_int_const(e) is not None for e in node.comparators[0].elts):
            # `x in (2, 3)` of an int: compared in C (the display is never built)
            lv = nexpr(comp, node.left, ctx)
            r = utmp(ctx, BOOL)
            test = ' || '.join('%s == %s' % (lv, _c_const(_int_const(e))) for e in node.comparators[0].elts)
            ctx.emit('%s = %s(%s);' % (r, '!' if isinstance(node.ops[0], ast.NotIn) else '', test))
            return r
        if any(isinstance(o, (ast.In, ast.NotIn, ast.Is, ast.IsNot)) for o in node.ops):
            return unbox(ctx, comp._expr_plain(node, ctx), BOOL)
        r = utmp(ctx, BOOL)
        left = node.left
        lv = nexpr(comp, left, ctx)
        lt = ntype(comp, ctx, left)
        depth = 0
        for i, (op, right) in enumerate(zip(node.ops, node.comparators)):
            if i:
                _open(ctx, 'if (%s) {' % r)
                depth += 1
            rv = nexpr(comp, right, ctx)
            rt = ntype(comp, ctx, right)
            if (lt == FLOAT) == (rt == FLOAT):
                ctx.emit('%s = (%s %s %s);' % (r, lv, _CMP_C[type(op)], rv))
            else:
                _fallback(comp, ctx, _CMP_RT[type(op)], [(lv, lt), (rv, rt)], BOOL, r)
            lv, lt = rv, rt
        for _ in range(depth):
            _close(ctx)
        return r
    if isinstance(node, ast.BoolOp):
        r = utmp(ctx, BOOL)
        is_and = isinstance(node.op, ast.And)
        ctx.emit('%s = %s;' % (r, nexpr(comp, node.values[0], ctx)))
        for v in node.values[1:]:
            _open(ctx, 'if (%s%s) {' % ('' if is_and else '!', r))
            ctx.emit('%s = %s;' % (r, nexpr(comp, v, ctx)))
        for _ in node.values[1:]:
            _close(ctx)
        return r
    if isinstance(node, ast.IfExp):
        r = utmp(ctx, t)
        if ntype(comp, ctx, node.test) in SCALAR:
            cond = ntest(comp, node.test, ctx)
        else:
            cond = 'ail_obj_truthy(%s)' % comp.expr(node.test, ctx)
        _open(ctx, 'if (%s) {' % cond)
        ctx.emit('%s = %s;' % (r, nexpr(comp, node.body, ctx)))
        _close(ctx, '} else {')
        ctx.indent += 1
        ctx.emit('%s = %s;' % (r, nexpr(comp, node.orelse, ctx)))
        _close(ctx)
        return r
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        f = node.func.id
        if f in comp.uplan.spec:
            v, vt = call_spec(comp, f, node.args, ctx)
            return v
        if f in ('min', 'max') and _builtin(comp.uplan, fp, f):
            vals = [nexpr(comp, a, ctx) for a in node.args]
            r = utmp(ctx, t)
            ctx.emit('%s = %s;' % (r, vals[0]))
            for v in vals[1:]:
                ctx.emit('if (%s %s %s) %s = %s;' % (v, '<' if f == 'min' else '>', r, r, v))
            return r
        return unbox(ctx, comp._expr_plain(node, ctx), t)
    if _draw_of(comp.uplan, node) is not None:
        return _draw(comp, node, ctx, t)
    if isinstance(node, ast.Subscript):
        rows = getattr(ctx, 'u_rows', {})
        if isinstance(node.value, ast.Name) and node.value.id in rows:
            arr, i, k = rows[node.value.id]
            return '%s[%s][%d]' % (arr, i, _int_const(node.slice) % k)
        return _subscript(comp, node, ctx, t)
    raise Conflict((fp.name, '*'), 'no unboxed form for %s' % type(node).__name__)


_TAG = {INT: 'AIL_T_INT', FLOAT: 'AIL_T_FLOAT', BOOL: 'AIL_T_BOOL'}


def _elem_rv(e, t):
    if t == FLOAT:
        return 'ail_float_val(%s)' % e
    if t == BOOL:
        return '((%s).i != 0)' % e
    return '(%s).i' % e


def list_read(comp, ctx, node):
    """`xs[i]` where every value of xs is proven a list (unified_lists.py): read in C."""
    fp = getattr(ctx, 'u', None)
    return (fp is not None and isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load)
            and not isinstance(node.slice, ast.Slice)
            and comp.uplan.lstate.get((fp.name, id(node.value))) == 'list')


def _subscript(comp, node, ctx, t):
    fp = ctx.u
    ctag = 'AIL_T_TUPLE' if comp.uplan.lstate.get((fp.name, id(node.value))) == 'tuple' else 'AIL_T_LIST'
    return _subscript_tag(comp, node, ctx, t, ctag)


def _subscript_tag(comp, node, ctx, t, ctag):
    """`xs[i]` of a proven list: the element from the vector, in C (t: its proven scalar type, unboxed; None: the
    element itself, boxed). An index out of range, a non-int index, or a value that is not a list at all (None)
    goes to the general path's own getitem, which raises what it raises."""
    c = comp.expr(node.value, ctx)
    cv = ctx.tmp()
    ctx.emit('%s = %s;' % (cv, c))
    if ntype(comp, ctx, node.slice) == INT:
        iv, bidx = nexpr(comp, node.slice, ctx), None
    else:
        bidx = comp.expr(node.slice, ctx)
        iv = '(%s).i' % bidx
    ok = utmp(ctx, BOOL)
    kk = utmp(ctx, INT)
    scalar = t in SCALAR
    r = utmp(ctx, t) if scalar else ctx.tmp()
    ctx.emit('%s = 0;' % ok)
    _open(ctx, 'if (%s.tag == %s%s) {' % (cv, ctag, (' && %s.tag == AIL_T_INT' % bidx) if bidx else ''))
    ctx.emit('ail_vecobj *_uv = (ail_vecobj *)%s.o;' % cv)
    ctx.emit('%s = %s; if (%s < 0) %s += _uv->n;' % (kk, iv, kk, kk))
    if scalar:
        ctx.emit('if ((uint64_t)%s < (uint64_t)_uv->n && _uv->p[%s].tag == %s) { %s = %s; %s = 1; }'
                 % (kk, kk, _TAG[t], r, _elem_rv('_uv->p[%s]' % kk, t), ok))
    else:
        ctx.emit('if ((uint64_t)%s < (uint64_t)_uv->n) { %s = _uv->p[%s]; %s = 1; }' % (kk, r, kk, ok))
    _close(ctx)
    _open(ctx, 'if (!%s) {' % ok)
    # anything else (an index out of range, a bool, a slice object, an instance's __index__ ...): the general
    # path's own subscript code, as it would have run
    s = comp._subscript_with_key(node, cv, bidx if bidx else 'ail_box_int(%s)' % iv, ctx)
    if not scalar:
        ctx.emit('%s = %s;' % (r, s))
    else:
        ctx.emit('if (%s.tag != %s) { st = ail_raise_c(cx, AIL_B_RUNTIMEERROR, "AIL internal error: a list element '
                 'of another type than unified.py proved"); goto %s; }' % (s, _TAG[t], _err(ctx)))
        ctx.emit('%s = %s;' % (r, _elem_rv(s, t)))
    _close(ctx)
    return r


def _bytearray_read(comp, ctx, node):
    """`b[i]` where b is an instance of the prelude's bytearray (the front end's own class inference): the class has
    one list of ints, `_a`, and `__getitem__` returns `_a[i]` for an int index in range."""
    if not (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load)
            and not isinstance(node.slice, ast.Slice)):
        return False
    if os.environ.get('AIL_UNIFIED_BYTES') == '0':
        return False
    try:
        if 'bytearray' not in comp.classes or '_ail' in ctx.u.name:
            return False        # (the library code the compiler adds is not the program's)
        kind = comp.infer_kind(node.value, ctx)
        if kind and kind != 'instance:bytearray':
            return False            # a dict, a str, ... the general path knows what it is
        info = comp._resolve_method('bytearray', '__getitem__')
        return bool(info) and info['cname'] == 'pm_bytearray___getitem__' \
            and ast.dump(info['node']) == _prelude_bytearray_getitem()
    except Exception:
        return False


_PRELUDE_BA = []


def _prelude_bytearray_getitem():
    """The AST dump of the prelude's own bytearray.__getitem__ (a user class of that name does not match)."""
    if not _PRELUDE_BA:
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prelude_bytes.py'),
                   encoding='utf-8').read()
        dump = None
        for c in ast.parse(src).body:
            if isinstance(c, ast.ClassDef) and c.name == 'bytearray':
                for m in c.body:
                    if isinstance(m, ast.FunctionDef) and m.name == '__getitem__':
                        dump = ast.dump(m)
        _PRELUDE_BA.append(dump)
    return _PRELUDE_BA[0]


def _bytearray_subscript(comp, node, ctx):
    """The element of a bytearray instance read in C: the instance must be exactly the prelude's class with an `_a`
    list and an in-range non-negative int index holding an int; anything else is the general path's own subscript
    (the method call, with its slices, negative indexes, errors)."""
    c = comp.expr(node.value, ctx)
    cv = ctx.tmp()
    ctx.emit('%s = %s;' % (cv, c))
    bidx = comp.expr(node.slice, ctx)
    ok = utmp(ctx, BOOL)
    r = ctx.tmp()
    comp.rt_needs.add('ba_u')
    ctx.emit('%s = ail2u_ba_get(%s, %s, g_slots_arr[%d], &%s, g_attr__a);'
             % (ok, cv, bidx, comp._class_global_slot('bytearray'), r))
    _open(ctx, 'if (!%s) {' % ok)
    s2 = comp._subscript_with_key(node, cv, bidx, ctx)
    ctx.emit('%s = %s;' % (r, s2))
    _close(ctx)
    return r


def _is_random_class(comp, k):
    while k is not None and k in comp.classes:
        if k == 'Random':
            return True
        k = comp.classes[k]['base']
    return False


def _draw(comp, node, ctx, t):
    """`r.m(args)` of a draw (`_draw_of`), its result in a C local: the receiver's class is checked as the general
    path's dispatch checks it (the same AttributeError otherwise), the arguments are evaluated, then the generator
    state and the numeric arguments are checked in the order randrt.py's ail2r_* functions check them."""
    m = node.func.attr
    k = comp._inst_class(node.func.value, ctx)
    if m == 'choice' or (k is not None and not _is_random_class(comp, k)):
        return unbox(ctx, comp._expr_plain(node, ctx), t)       # whatever the general path does with it
    recv = comp.expr(node.func.value, ctx)
    rv = ctx.tmp()
    ctx.emit('%s = %s;' % (rv, recv))
    err = _err(ctx)
    ctx.emit('if (!(%s.tag == AIL_T_INST && ail_class_is_or_subclass(((ail_instobj *)%s.o)->cls, g_slots_arr[%d]))) '
             '{ st = ail_raise_c(cx, AIL_B_ATTRIBUTEERROR, "object has no attribute \'%s\'"); goto %s; }'
             % (rv, rv, comp.global_slots['class:Random'], m, err))
    args = []
    for a in node.args:
        at = ntype(comp, ctx, a)
        if at in SCALAR:
            args.append((nexpr(comp, a, ctx), at))
        else:
            args.append((comp.expr(a, ctx), OBJ))
    L = ctx.tmp()
    ctx.emit('st = ail_inst_getattr(cx, &%s, %s, g_attr_mt, "mt");' % (L, rv))
    ctx.check()
    r = utmp(ctx, t)
    if t == INT:
        boxed = [v if at == OBJ else box(comp, ctx, v, at) for v, at in args]
        s = ctx.tmp()
        if m == 'getrandbits':
            ctx.emit('st = ail2r_bits(cx, &%s, %s, %s);' % (s, L, boxed[0]))
        else:
            if m == 'randint':
                boxed += ['ail_box_int(1LL)', 'ail_box_int(1LL)']
            else:
                boxed += ['ail_box_none()', 'ail_box_int(1LL)'][len(boxed) - 1:] + ['ail_box_int(0LL)']
            ctx.emit('st = ail2r_range(cx, &%s, %s, %s);' % (s, L, ', '.join(boxed)))
        ctx.check()
        ctx.emit('%s = (%s).i;' % (r, s))
        return r
    comp.rt_needs.add('rng_u')
    p = ctx.new_cvar('urp')
    ctx.u_decls.append('ail_obj *%s = NULL;' % p)
    ctx.emit('st = ail2r_state(cx, %s, &%s);' % (L, p))
    ctx.check()
    ds = []
    for v, at in args:
        if at == OBJ:
            d = utmp(ctx, FLOAT)
            ctx.emit('if (!ail2r_num(%s, &%s)) { st = ail2r_need_num(cx, %s, &%s); goto %s; }' % (v, d, v, d, err))
            ds.append(d)
        else:
            ds.append(_f(v, at))
    if m == 'random':
        ctx.emit('%s = ail2r_rand(%s);' % (r, p))
    elif m == 'expovariate':
        ctx.emit('st = ail2r_expo_u(cx, &%s, %s, %s);' % (r, p, ds[0]))
        ctx.check()
    elif m == 'gauss':
        ds += ['0.0', '1.0'][len(ds):]
        ctx.emit('%s = ail2r_gauss_u(%s, %s, %s);' % (r, p, ds[0], ds[1]))
    else:       # uniform(a, b): a + (b - a) * random(), b - a exact when both are ints
        (a, at), (b, bt) = args
        if at in (INT, BOOL) and bt in (INT, BOOL):
            diff = '(double)((__int128)%s - (__int128)%s)' % (b, a)
        elif FLOAT in (at, bt):
            diff = '(%s - %s)' % (ds[1], ds[0])
        else:
            ba = a if at == OBJ else _box_rv(at, a)
            bb = b if bt == OBJ else _box_rv(bt, b)
            diff = 'ail2r_diff(%s, %s)' % (bb, ba)
        ctx.emit('%s = ail2r_uniform_u(%s, %s, %s);' % (r, p, ds[0], diff))
    return r


def _binop(comp, node, ctx, t):
    if t == INT:
        constant = int_constant(node)
        if type(constant) is int and -(1 << 63) <= constant < (1 << 63):
            return _c_const(constant)
    op = node.op
    lt, rt = ntype(comp, ctx, node.left), ntype(comp, ctx, node.right)
    a = nexpr(comp, node.left, ctx)
    b = nexpr(comp, node.right, ctx)
    r = utmp(ctx, t)
    fn = _BIN_RT[type(op)]
    ops = [(a, lt), (b, rt)]

    def guarded(cond, fast):
        _open(ctx, 'if (%s) {' % cond)
        _fallback(comp, ctx, fn, ops, t, r)
        _close(ctx, '} else {')
        ctx.indent += 1
        for line in fast:
            ctx.emit(line)
        _close(ctx)

    if lt == INT and rt == INT:
        c = node.right.value if isinstance(node.right, ast.Constant) and isinstance(node.right.value, int) \
            and not isinstance(node.right.value, bool) else None
        if c is not None and c > 0 and c & (c - 1) == 0 and isinstance(op, (ast.FloorDiv, ast.Mod)):
            # floor semantics on two's complement: x // 2**k is the arithmetic shift, x % 2**k the mask
            k = c.bit_length() - 1
            if isinstance(op, ast.FloorDiv):
                ctx.emit('%s = %s >> %d;' % (r, a, k))
            else:
                ctx.emit('%s = %s & %dLL;' % (r, a, c - 1))
            return r
        if type(op) in _OVF:
            _open(ctx, 'if (__builtin_%s_overflow(%s, %s, &%s)) {' % (_OVF[type(op)], a, b, r))
            _fallback(comp, ctx, fn, ops, t, r)
            _close(ctx)
        elif isinstance(op, ast.FloorDiv):
            guarded('%s == 0 || (%s == INT64_MIN && %s == -1)' % (b, a, b),
                    ['%s = %s / %s;' % (r, a, b),
                     'if ((%s %% %s != 0) && (((%s %% %s) < 0) != (%s < 0))) %s -= 1;' % (a, b, a, b, b, r)])
        elif isinstance(op, ast.Mod):
            guarded('%s == 0 || %s == -1' % (b, b),
                    ['%s = %s %% %s;' % (r, a, b),
                     'if (%s != 0 && ((%s < 0) != (%s < 0))) %s += %s;' % (r, r, b, r, b)])
        elif isinstance(op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
            ctx.emit('%s = %s %s %s;' % (r, a, {ast.BitAnd: '&', ast.BitOr: '|', ast.BitXor: '^'}[type(op)], b))
        elif isinstance(op, ast.LShift):
            guarded('!(%s >= 0 && %s < 63) || (((int64_t)((uint64_t)%s << %s)) >> %s) != %s' % (b, b, a, b, b, a),
                    ['%s = (int64_t)((uint64_t)%s << %s);' % (r, a, b)])
        elif isinstance(op, ast.RShift):
            guarded('%s < 0' % b, ['%s = %s >= 63 ? (%s < 0 ? -1 : 0) : (%s >> %s);' % (r, b, a, a, b)])
        elif isinstance(op, ast.Div):
            guarded('%s == 0' % b, ['%s = (double)%s / (double)%s;' % (r, a, b)])
        else:
            raise Conflict((ctx.u.name, '*'), 'int operator %s' % type(op).__name__)
        return r
    # float (an int operand converts, as the runtime's ail__as_double does)
    x, y = _f(a, lt), _f(b, rt)
    if isinstance(op, (ast.Add, ast.Sub, ast.Mult)):
        ctx.emit('%s = %s %s %s;' % (r, x, {ast.Add: '+', ast.Sub: '-', ast.Mult: '*'}[type(op)], y))
    elif isinstance(op, ast.Div):
        guarded('%s == 0.0' % y, ['%s = %s / %s;' % (r, x, y)])
    elif isinstance(op, ast.FloorDiv):
        guarded('%s == 0.0' % y, ['%s = ail_obj2_ffloormod(%s, %s, 0);' % (r, x, y)])
    elif isinstance(op, ast.Mod):
        guarded('%s == 0.0' % y, ['%s = ail_obj2_ffloormod(%s, %s, 1);' % (r, x, y)])
    else:
        raise Conflict((ctx.u.name, '*'), 'float operator %s' % type(op).__name__)
    return r


def call_spec(comp, name, args, ctx):
    """A call of specialised function `name`: (C value, lattice value of the result). Boxed parameters get
    the general path's boxed argument; unboxed ones the native value."""
    callee = comp.uplan.spec[name]
    fp = getattr(ctx, 'u', None)
    argcs = []
    for a, pt in zip(args, callee.ptypes):
        if pt in SCALAR:
            if fp is None or ntype(comp, ctx, a) != pt:
                raise Conflict((callee.name, '*'), 'argument of another type at a call site')
            argcs.append(nexpr(comp, a, ctx))
        else:
            argcs.append(comp.expr(a, ctx))
    call = '%s(cx, &%%s%s)' % (callee.name, ''.join(', ' + x for x in argcs))
    if callee.ret in SCALAR and fp is None:
        # module code (or a function left boxed) calling a function with an unboxed result: box it here
        s = ctx.tmp()
        ctx.emit('{ %s _ur; st = %s;' % (CTYPE[callee.ret], call % '_ur'))
        ctx.emit('  if (st != AIL_OK) goto %s;' % _err(ctx))
        ctx.emit('  %s = %s; }' % (s, _box_rv(callee.ret, '_ur')))
        return s, OBJ
    r = utmp(ctx, callee.ret) if callee.ret in SCALAR else ctx.tmp()
    ctx.emit('st = %s;' % (call % r))
    ctx.check()
    return r, callee.ret


def boxed_body_hook(comp, name):
    """The general path is about to call (or take the value of) the boxed body of `name`."""
    plan = comp.uplan
    if name in plan.spec and name not in plan.need_generic:
        raise Conflict((plan.spec[name].name, '*'), 'the boxed body was left out but is called')


def name_ref_hook(comp, name, ctx):
    fp = getattr(ctx, 'u', None)
    if fp is not None and name in fp.locals and fp.unboxed(name):
        raise Conflict((fp.name, name), 'the frame slot of an unboxed variable was asked for')


def _assign_native(comp, ctx, target, v, t):
    fp = ctx.u
    if fp.unboxed(target.id):
        if fp.vtype[target.id] != t:
            raise Conflict((fp.name, target.id), 'a %s stored in a %s variable' % (t, fp.vtype[target.id]))
        ctx.emit('%s = %s;' % (fp.cvar(target.id), v))
    else:
        comp._assign_target(target, box(comp, ctx, v, t), ctx, value_kind=KIND[t])
        comp.set_kind(target.id, KIND[t], ctx)
        comp.set_elem_kind(target.id, None, ctx)


def stmt_hook(comp, node, ctx):
    """pyboxed2.stmt: True when the statement was emitted here."""
    fp = getattr(ctx, 'u', None)
    if fp is None:
        return False
    if _pair_assign(node) and any(e.id in fp.locals and fp.unboxed(e.id) for e in node.targets[0].elts):
        # every value first (into temporaries: `a, b = b, a`), then the names left to right
        vals = []
        for tg, v in zip(node.targets[0].elts, node.value.elts):
            if tg.id in fp.locals and fp.unboxed(tg.id):
                t = ntype(comp, ctx, v)
                if t != fp.vtype[tg.id]:
                    raise Conflict((fp.name, tg.id), 'a %s stored in a %s variable' % (t, fp.vtype[tg.id]))
                x = nexpr(comp, v, ctx)
                tmp = utmp(ctx, t)
                ctx.emit('%s = %s;' % (tmp, x))
                vals.append((tg, tmp, True))
            else:
                b = comp.expr(v, ctx)
                s = ctx.tmp()
                ctx.emit('%s = %s;' % (s, b))
                vals.append((tg, s, False))
        for tg, x, native in vals:
            if native:
                ctx.emit('%s = %s;' % (fp.cvar(tg.id), x))
            else:
                comp._assign_target(tg, x, ctx)
                comp.set_kind(tg.id, None, ctx)
        return True
    if _unpackable(node) and _unpack_assign(comp, node, ctx):
        return True
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if node.value is None or not all(isinstance(x, ast.Name) for x in targets):
            return False
        if not any(x.id in fp.locals and fp.unboxed(x.id) for x in targets):
            return False
        t = ntype(comp, ctx, node.value)
        if t not in SCALAR:
            raise Conflict((fp.name, targets[0].id), 'a boxed value stored in an unboxed variable')
        if isinstance(node, ast.AnnAssign):
            comp._declare_if_local(node.target.id, ctx)
        v = nexpr(comp, node.value, ctx)
        for x in targets:
            _assign_native(comp, ctx, x, v, t)
        return True
    if isinstance(node, ast.AugAssign):
        if not (isinstance(node.target, ast.Name) and node.target.id in fp.locals and fp.unboxed(node.target.id)):
            return False
        virt = ast.copy_location(ast.BinOp(left=ast.Name(id=node.target.id, ctx=ast.Load()), op=node.op,
                                           right=node.value), node)
        t = ntype(comp, ctx, virt)
        if t != fp.vtype[node.target.id]:
            raise Conflict((fp.name, node.target.id), 'augmented assignment changes the type')
        ctx.emit('%s = %s;' % (fp.cvar(node.target.id), nexpr(comp, virt, ctx)))
        return True
    if isinstance(node, ast.If):
        if comp._is_main_guard(node) or ntype(comp, ctx, node.test) not in SCALAR:
            return False
        _open(ctx, 'if (%s) {' % ntest(comp, node.test, ctx))
        comp.block(node.body, ctx)
        if node.orelse:
            _close(ctx, '} else {')
            ctx.indent += 1
            comp.block(node.orelse, ctx)
        _close(ctx)
        return True
    if isinstance(node, ast.While):
        if ntype(comp, ctx, node.test) not in SCALAR:
            return False
        has_else = bool(node.orelse)
        broke = ctx.new_cvar('broke') if has_else else None
        if has_else:
            ctx.emit('int %s = 0;' % broke)
        ctx.loop_stack.append({'has_else': has_else, 'broke': broke, 'finally_depth': len(ctx.finally_stack)})
        _open(ctx, 'while (1) {')
        comp._gil_check(ctx)
        ctx.emit('if (!%s) break;' % ntest(comp, node.test, ctx))
        comp.block(node.body, ctx)
        _close(ctx)
        ctx.loop_stack.pop()
        if has_else:
            _open(ctx, 'if (!%s) {' % broke)
            comp.block(node.orelse, ctx)
            _close(ctx)
        return True
    if isinstance(node, ast.For) and _const_loop(comp, node, ctx):
        return True
    if isinstance(node, ast.For) and _vector_loop(comp, node, ctx):
        return True
    if isinstance(node, ast.For) and _tuple_loop(comp, node, ctx):
        return True
    if isinstance(node, ast.For):
        tg = node.target
        if not (isinstance(tg, ast.Name) and tg.id in fp.locals and fp.unboxed(tg.id)
                and _is_range_call(node.iter, comp.uplan.fn_names)):
            return False
        if fp.vtype[tg.id] != INT:
            raise Conflict((fp.name, tg.id), 'a range loop variable that is not an int')
        args = node.iter.args
        native = all(ntype(comp, ctx, a) == INT for a in args)
        step = 1
        if len(args) == 3:
            s = args[2]
            if isinstance(s, ast.UnaryOp) and isinstance(s.op, ast.USub) and isinstance(s.operand, ast.Constant):
                step = -s.operand.value if isinstance(s.operand.value, int) else 0
            elif isinstance(s, ast.Constant) and isinstance(s.value, int) and not isinstance(s.value, bool):
                step = s.value
            else:
                step = 0
            if step == 0 or isinstance(step, bool):
                native = False
        has_else = bool(node.orelse)
        broke = ctx.new_cvar('broke') if has_else else None
        if has_else:
            ctx.emit('int %s = 0;' % broke)
        ctx.loop_stack.append({'has_else': has_else, 'broke': broke, 'finally_depth': len(ctx.finally_stack)})
        if native:
            vals = [nexpr(comp, a, ctx) for a in args[:2]]
            lo, hi = ('0', vals[0]) if len(args) == 1 else (vals[0], vals[1])
            n = ctx.new_cvar('un')
            k = ctx.new_cvar('uk')
            lo_v = ctx.new_cvar('ulo')
            ctx.emit('int64_t %s = %s;' % (lo_v, lo))
            if step > 0:
                ctx.emit('uint64_t %s = %s < %s ? ((uint64_t)%s - (uint64_t)%s - 1) / %dULL + 1 : 0;'
                         % (n, lo_v, hi, hi, lo_v, step))
            else:
                ctx.emit('uint64_t %s = %s > %s ? ((uint64_t)%s - (uint64_t)%s - 1) / %dULL + 1 : 0;'
                         % (n, lo_v, hi, lo_v, hi, -step))
            _open(ctx, 'for (uint64_t %s = 0; %s < %s; %s++) {' % (k, k, n, k))
            comp._gil_check(ctx)
            if step == 1:
                ctx.emit('%s = (int64_t)((uint64_t)%s + %s);' % (fp.cvar(tg.id), lo_v, k))
            else:
                ctx.emit('%s = (int64_t)((uint64_t)%s + %s * (uint64_t)(%dLL));' % (fp.cvar(tg.id), lo_v, k, step))
        else:
            val = comp._open_iter_loop(node.iter, ctx)
            ctx.emit('%s = (%s).i;' % (fp.cvar(tg.id), val))
        comp.block(node.body, ctx)
        _close(ctx)
        ctx.loop_stack.pop()
        if has_else:
            _open(ctx, 'if (!%s) {' % broke)
            comp.block(node.orelse, ctx)
            _close(ctx)
        return True
    if isinstance(node, ast.Return):
        if not (fp.spec and fp.ret in SCALAR):
            return False
        if node.value is None or ctx.finally_stack or ntype(comp, ctx, node.value) != fp.ret:
            raise Conflict((fp.name, '*'), 'a return of another type')
        ctx.emit('*out = %s;' % nexpr(comp, node.value, ctx))
        ctx.emit('AIL_FRAME_LEAVE(cx, f);')
        ctx.emit('return AIL_OK;')
        return True
    return False


def _vector_loop(comp, node, ctx):
    """`for x in xs` where xs is proven a list of scalars of x's type (unified_lists.py): walk the vector in C,
    as CPython's list iterator does (the length is read again at every step, so a list changed by the body is
    walked as CPython walks it)."""
    fp = ctx.u
    plan = comp.uplan
    tg = node.target
    if not (isinstance(tg, ast.Name) and tg.id in fp.locals and fp.unboxed(tg.id) and _local_iter(fp, node.iter)):
        return False
    key = (fp.name, id(node.iter))
    t = fp.vtype[tg.id]
    if plan.lstate.get(key) != 'list' or plan.lelem.get(key) != t:
        return False
    c = comp.expr(node.iter, ctx)
    cv = ctx.tmp()
    ctx.emit('%s = %s;' % (cv, c))
    err = _err(ctx)
    # a proven list class may also hold None: iterating that raises what the general path raises
    s = ctx.tmp()
    ctx.emit('if (%s.tag != AIL_T_LIST) { st = ail_iter(cx, &%s, %s); if (st == AIL_OK) st = ail_raise_c(cx, '
             'AIL_B_RUNTIMEERROR, "AIL internal error: a loop over a value unified.py proved a list"); goto %s; }'
             % (cv, s, cv, err))
    has_else = bool(node.orelse)
    broke = ctx.new_cvar('broke') if has_else else None
    if has_else:
        ctx.emit('int %s = 0;' % broke)
    ctx.loop_stack.append({'has_else': has_else, 'broke': broke, 'finally_depth': len(ctx.finally_stack)})
    k = ctx.new_cvar('uvk')
    _open(ctx, 'for (int64_t %s = 0;; %s++) {' % (k, k))
    ctx.emit('ail_vecobj *_uv = (ail_vecobj *)%s.o;' % cv)
    ctx.emit('if (%s >= _uv->n) break;' % k)
    ctx.emit('if (_uv->p[%s].tag != %s) { st = ail_raise_c(cx, AIL_B_RUNTIMEERROR, "AIL internal error: a list '
             'element of another type than unified.py proved"); goto %s; }' % (k, _TAG[t], err))
    ctx.emit('%s = %s;' % (fp.cvar(tg.id), _elem_rv('_uv->p[%s]' % k, t)))
    comp._gil_check(ctx)
    comp.block(node.body, ctx)
    _close(ctx)
    ctx.loop_stack.pop()
    if has_else:
        _open(ctx, 'if (!%s) {' % broke)
        comp.block(node.orelse, ctx)
        _close(ctx)
    return True


def _unpack_assign(comp, node, ctx):
    """`a, b = value` where value is proven a tuple of that many components (unified_lists.py, state P): read the
    components in place; a name with a proven scalar type is unboxed."""
    fp = ctx.u
    plan = comp.uplan
    names = node.targets[0].elts
    if not all(e.id in fp.locals for e in names):
        return False
    tp = unpack_types(plan, fp, node)
    if tp is None or 'bot' in tp:
        if any(fp.unboxed(e.id) for e in names):
            raise Conflict((fp.name, names[0].id), 'an unpacking that was not proven')
        return False
    for e, tt in zip(names, tp):
        if fp.unboxed(e.id) and (tt not in SCALAR or fp.vtype[e.id] != tt):
            raise Conflict((fp.name, e.id), 'an unpacked name of another type than proven')
    err = _err(ctx)
    c = comp.expr(node.value, ctx)
    cv = ctx.tmp()
    ctx.emit('%s = %s;' % (cv, c))
    ctx.emit('if (%s.tag != AIL_T_TUPLE || ((ail_vecobj *)%s.o)->n != %d) { st = ail_raise_c(cx, '
             'AIL_B_RUNTIMEERROR, "AIL internal error: an unpacked value of another shape than unified.py proved"); '
             'goto %s; }' % (cv, cv, len(names), err))
    v = ctx.new_cvar('upv')
    ctx.emit('ail_vecobj *%s = (ail_vecobj *)%s.o;' % (v, cv))
    elems = ['%s->p[%d]' % (v, i) for i in range(len(names))]
    for e, tt, x in zip(names, tp, elems):
        if fp.unboxed(e.id):
            ctx.emit('if (%s.tag != %s) { st = ail_raise_c(cx, AIL_B_RUNTIMEERROR, "AIL internal error: a tuple '
                     'component of another type than unified.py proved"); goto %s; }' % (x, _TAG[tt], err))
    for e, tt, x in zip(names, tp, elems):
        if fp.unboxed(e.id):
            ctx.emit('%s = %s;' % (fp.cvar(e.id), _elem_rv(x, tt)))
        else:
            sv = ctx.tmp()
            ctx.emit('%s = %s;' % (sv, x))
            comp._assign_target(e, sv, ctx)
            comp.set_kind(e.id, None, ctx)
    return True


def _tuple_loop(comp, node, ctx):
    """`for a, b in zip(xs, ys)` where xs and ys are proven lists, or `for a, b in ps` where ps is a proven list of
    proven pairs (unified_lists.py, state P): walk the vectors in C and bind the names straight from the elements
    (no tuple is built for a zip; a pair is read in place). A name with a proven scalar type is unboxed. The lists are
    walked as CPython's list iterators walk them: the length is read again at every step, and a zip stops at the
    first list that has no element left."""
    fp = ctx.u
    plan = comp.uplan
    tg = node.target
    if not (isinstance(tg, ast.Tuple) and all(isinstance(e, ast.Name) and e.id in fp.locals for e in tg.elts)):
        return False
    names = tg.elts
    n = len(names)
    tpk = tloop_types(plan, fp, node)
    if tpk is None or 'bot' in tpk[1]:
        if any(fp.unboxed(e.id) for e in names):
            raise Conflict((fp.name, names[0].id), 'a tuple loop that was not proven')
        return False
    kind, tp = tpk
    for e, tt in zip(names, tp):
        if fp.unboxed(e.id) and (tt not in SCALAR or fp.vtype[e.id] != tt):
            raise Conflict((fp.name, e.id), 'a tuple loop name of another type than proven')
    err = _err(ctx)
    zipped = kind == 'zip'
    args = node.iter.args if zipped else [node.iter.args[0] if kind == 'enum' else node.iter]
    start = node.iter.args[1].value if kind == 'enum' and len(node.iter.args) == 2 else 0
    cvs = []
    for a in args:
        c = comp.expr(a, ctx)
        cv = ctx.tmp()
        ctx.emit('%s = %s;' % (cv, c))
        cvs.append(cv)
    for cv in cvs:
        sl = ctx.tmp()
        ctx.emit('if (%s.tag != AIL_T_LIST) { st = ail_iter(cx, &%s, %s); if (st == AIL_OK) st = ail_raise_c(cx, '
                 'AIL_B_RUNTIMEERROR, "AIL internal error: a loop over a value unified.py proved a list"); '
                 'goto %s; }' % (cv, sl, cv, err))
    has_else = bool(node.orelse)
    broke = ctx.new_cvar('broke') if has_else else None
    if has_else:
        ctx.emit('int %s = 0;' % broke)
    ctx.loop_stack.append({'has_else': has_else, 'broke': broke, 'finally_depth': len(ctx.finally_stack)})
    k = ctx.new_cvar('utk')
    _open(ctx, 'for (int64_t %s = 0;; %s++) {' % (k, k))
    elems = []
    if zipped:
        for i, cv in enumerate(cvs):
            v = ctx.new_cvar('utv')
            ctx.emit('ail_vecobj *%s = (ail_vecobj *)%s.o;' % (v, cv))
            ctx.emit('if (%s >= %s->n) break;' % (k, v))
            elems.append('%s->p[%s]' % (v, k))
    elif kind == 'enum':
        v = ctx.new_cvar('utv')
        ctx.emit('ail_vecobj *%s = (ail_vecobj *)%s.o;' % (v, cvs[0]))
        ctx.emit('if (%s >= %s->n) break;' % (k, v))
        elems = ['ail_box_int(%s + (%dLL))' % (k, start), '%s->p[%s]' % (v, k)]
    else:
        v = ctx.new_cvar('utv')
        ctx.emit('ail_vecobj *%s = (ail_vecobj *)%s.o;' % (v, cvs[0]))
        ctx.emit('if (%s >= %s->n) break;' % (k, v))
        tv = ctx.new_cvar('utt')
        ctx.emit('ail_obj %s_e = %s->p[%s];' % (tv, v, k))
        ctx.emit('if (%s_e.tag != AIL_T_TUPLE || ((ail_vecobj *)%s_e.o)->n != %d) { st = ail_raise_c(cx, '
                 'AIL_B_RUNTIMEERROR, "AIL internal error: a list element of another shape than unified.py proved"); '
                 'goto %s; }' % (tv, tv, n, err))
        ctx.emit('ail_vecobj *%s = (ail_vecobj *)%s_e.o;' % (tv, tv))
        elems = ['%s->p[%d]' % (tv, i) for i in range(n)]
    for e, tt, x in zip(names, tp, elems):
        if fp.unboxed(e.id):
            ctx.emit('if (%s.tag != %s) { st = ail_raise_c(cx, AIL_B_RUNTIMEERROR, "AIL internal error: a tuple '
                     'component of another type than unified.py proved"); goto %s; }' % (x, _TAG[tt], err))
    for e, tt, x in zip(names, tp, elems):
        if fp.unboxed(e.id):
            ctx.emit('%s = %s;' % (fp.cvar(e.id), _elem_rv(x, tt)))
        else:
            sv = ctx.tmp()
            ctx.emit('%s = %s;' % (sv, x))
            comp._assign_target(e, sv, ctx)
            comp.set_kind(e.id, None, ctx)
    comp._gil_check(ctx)
    comp.block(node.body, ctx)
    _close(ctx)
    ctx.loop_stack.pop()
    if has_else:
        _open(ctx, 'if (!%s) {' % broke)
        comp.block(node.orelse, ctx)
        _close(ctx)
    return True


def _const_loop(comp, node, ctx):
    """`for x in (-1, 0, 1)` / `for dx, dy in ((1, 0), (0, 1))` / `for a, b in TABLE` (a module table, see analyze)
    with every target an unboxed int: a loop over a static C array."""
    fp = ctx.u
    plan = comp.uplan
    tg = node.target
    rowvar = None
    if isinstance(tg, ast.Name) and tg.id in fp.rowvars and fp.rowvars[tg.id] is node:
        rows = rows_any(plan, fp, node.iter)
        if rows in (None, 'bot') or len(rows[0]) < 2:
            return False
        rowvar, names = tg.id, []
    else:
        names = [tg] if isinstance(tg, ast.Name) else (list(tg.elts) if isinstance(tg, ast.Tuple) else None)
        if not names or not all(isinstance(e, ast.Name) and e.id in fp.locals and fp.unboxed(e.id)
                                and fp.vtype[e.id] == INT for e in names):
            return False
        rows = const_rows(plan, fp, node.iter, len(names) if isinstance(tg, ast.Tuple) else 1)
        if rows is None:
            return False
    if isinstance(node.iter, ast.Name):
        comp.expr(node.iter, ctx)       # the read of the table itself: NameError / UnboundLocalError as before
    arr = ctx.new_cvar('uct')
    k = len(rows[0])
    ctx.emit('static const int64_t %s[%d][%d] = { %s };' % (
        arr, len(rows), k, ', '.join('{ %s }' % ', '.join(_c_const(v) for v in row) for row in rows)))
    has_else = bool(node.orelse)
    broke = ctx.new_cvar('broke') if has_else else None
    if has_else:
        ctx.emit('int %s = 0;' % broke)
    ctx.loop_stack.append({'has_else': has_else, 'broke': broke, 'finally_depth': len(ctx.finally_stack)})
    i = ctx.new_cvar('uci')
    _open(ctx, 'for (int %s = 0; %s < %d; %s++) {' % (i, i, len(rows), i))
    comp._gil_check(ctx)
    for j, e in enumerate(names):
        ctx.emit('%s = %s[%s][%d];' % (fp.cvar(e.id), arr, i, j))
    if rowvar is not None:
        # the row itself is never built: every read of it is `r[c]`, which reads the array
        if not hasattr(ctx, 'u_rows'):
            ctx.u_rows = {}
        ctx.u_rows[rowvar] = (arr, i, k)
    comp.block(node.body, ctx)
    if rowvar is not None:
        del ctx.u_rows[rowvar]
    _close(ctx)
    ctx.loop_stack.pop()
    if has_else:
        _open(ctx, 'if (!%s) {' % broke)
        comp.block(node.orelse, ctx)
        _close(ctx)
    return True


def record(plan, demoted):
    entry = dict(plan.stats, demoted=sorted('%s:%s' % k for k in demoted), reasons=list(_REASONS))
    del _REASONS[:]
    STATS.append(entry)
    target = os.environ.get('AIL_UNIFIED_STATS')
    if target:
        import json
        with open(target, 'a') as handle:
            handle.write(json.dumps(entry) + '\n')
