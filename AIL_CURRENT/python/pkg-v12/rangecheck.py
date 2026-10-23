"""Value-range analysis that proves int64 overflow checks and list index checks cannot fire.

`int` is 64-bit and `a + b`, `a - b`, `a * b` raise OverflowError when the exact result leaves
int64 (`ck_add`/`ck_sub`/`ck_mul`); `xs[i]` on a list, float list or bytes value raises IndexError
outside [-len, len) (`ail_list_get` & co.). Both checks are one compare and branch, but in the
innermost loop of an LLM-written program they are most of the loop (a grid-life program: 65% of all
instructions). This pass proves, per AST node, that a check cannot fire, and `pyfunc` then emits
the plain operation. It never changes what a program does: a node is marked only when EVERY
execution reaching it is proven in range; anything the rules below do not cover keeps its check.

The analysis runs per function, after the body was compiled (so every name's kind is settled), on
the Python AST that function was compiled from. It is an abstract interpreter over the statements
in source order, flow-sensitive, intraprocedural.

Abstract state, at every program point: for each tracked symbol
    [lo, hi]                numeric bounds (Python ints, so the analysis itself never overflows)
    ub = {s: c}             symbol <= s + c, for other symbols s
    lb = {s: c}             symbol >= s + c
A missing symbol is "anything". Symbols are:
    an int-kind local or parameter                         (parameters are never reassigned in AIL)
    '#len:X'   the length of X: a bytes local or parameter (immutable: changes only when X is
               rebound), or a list/float-list local that is NEVER aliased -- every binding of X is
               a fresh list (a literal, `[e] * n`, a comprehension, list()/sorted(), or `X = Y`
               between two plain int-list locals, which this compiler compiles as a COPY, see
               pyfunc `_assign` and SEMANTICS.md section 5a), and X appears only as X[i], len(X),
               `for v in X`, `v in X`, a few read-only built-ins, the right side of such a copy, or
               the receiver of its own method calls. A list passed to a call, stored in a field,
               bound by a tuple/for/with target, sliced on the left, `del`eted, etc. is never
               tracked: then no other name can reach its buffer, so only statements of this
               function, all seen here, change its length.
    '#lo@N' / '#hi@N' / '#k@N'  the bounds of the N-th `for _ in range(a, b)`, fixed when the
               loop starts, and its hidden counter (the loop runs as `k = a; while k < b
               { i = k; body; k += 1 }`).
    '#fld:o.f' the int field f of an unaliased object parameter o; '#len:#fld:o.f' the length of
               its bytes/list field. o is tracked only when every use of it is `o.f` or
               `o.method(...)`, so no other name of this function can reach f; a store to a field,
               an unknown method call, or any unanalysed construct forgets its facts.

Value rules (an expression's abstract value has the same shape):
    int literals, module int constants: exact.        True/False, comparisons, `not`: [0, 1].
    b[i] of bytes/bytearray, iterating bytes:  [0, 255].      ord(c): [0, 0x10FFFF].
    len(...) of a container: [0, 2**48]. A materialised container longer than 2**48 elements
        would need at least 256 TiB of memory touched by the program before the length existed,
        so the allocation fails (and the program stops) long before.
    x % m with m >= 1: [0, m - 1] and x % m <= m - 1.          x & c with c >= 0: [0, c].
    x // k, x >> k, x << k (constant k), abs/min/max, unary minus, | and ^ of non-negatives:
        interval rules. find/rfind/count on str/bytes: [-1, 2**48] / [0, 2**48].
    a + b, a - b, a * b: exact interval arithmetic (on Python ints); a +/- constant keeps every
        symbolic bound shifted by the constant; a - b is also bounded through a shared symbol
        (b <= s + c and a >= s + d  =>  a - b >= d - c), and between two exact symbols it records
        the identity `a - b == sa - sb`, so a later guard on the difference (e.g. `available < 4`)
        refines the operands themselves (`position <= len - 4`).
    After a checked operation the value is in int64 (otherwise it raised), so results are clipped.
    X[i] of a tracked int list: the union of every value ever stored into X (its fresh value,
        X[j] = v, X[j] op= v, append/insert); found by re-running the whole analysis until that
        union is stable (Kleene iteration from "nothing stored"; only the stable run's proofs are
        kept, and anything unanalysed that may store into X makes its elements unknown).
    The loop variable of `for i in range(a, b)` (step absent or 1) equals the counter k, which
        satisfies #lo@N <= k <= #hi@N - 1 in the body.

Statement rules: `x = e` replaces x's facts (and every fact mentioning x; `x = x + c` shifts
them instead); `X.append(v)`, `X.insert(i, v)`, `X.pop()` as statements that do not mention X
otherwise shift #len:X by exactly +1/-1 (any other method call forgets #len:X before its
statement); `o.m()` for a zero-argument method whose body is only guards and a return, with no
assignment, loop, try or call outside the pure builtins, is analysed in place against the
caller's field facts, so its guard proves facts for the caller (this is how `remaining()` gives
`read_u8` its `position <= len - 1`); `if`/`while`/`assert` tests refine the state on each branch
(<, <=, >, >=, ==, != between int expressions -- never a float or text comparison -- with `and`/`or`/`not`, including
inside short-circuit operands); joins keep only facts true on both sides (a fact missing on one
side is kept when that side's numeric bounds imply it); loops iterate to a fixed point with
widening (bounds that keep moving go to int64's ends, symbolic facts that weaken are dropped),
then try one narrowing step that is kept only if it is itself an invariant; at loop entry symbols
with an exact value are related to the counter by their difference; break/continue/return/raise
are followed; an exception handler starts from the state before its `try` with every name the
try body may assign (and every list it mentions) forgotten; a `finally` starts from the same
over the whole statement (a break/continue through a `finally` aborts the analysis). Anything
else (an unknown statement, a nested function, `global`, a comprehension variable, a walrus)
forgets every name it could assign, and nodes inside unknown constructs are never marked.

What is marked:
    a + b, a - b, a * b, x += e, x -= e, x *= e on ints   when the exact result is provably in
                                                          [-2**63, 2**63 - 1]
    X[i] read or store, X a tracked list/float list/bytes  when 0 <= i and i <= #len:X - 1 are
                                                          provable (directly, through up to three
                                                          symbolic steps, or numerically)
Every proof is the AND over all the times the node is analysed with recording on, and loops
record only on their final pass over the fixed point. A budget bounds the work; exceeding it
gives up on the whole function (nothing is marked).
"""
import ast
import os
import sys
import time

_DEBUG = bool(os.environ.get('AIL_RANGE_DEBUG'))
MIN = -(1 << 63)
MAX = (1 << 63) - 1
LENMAX = 1 << 48            # no materialised container can hold more elements than this
TOP = (MIN, MAX, {}, {})
_ARITH = (ast.Add, ast.Sub, ast.Mult)
_BUDGET = int(os.environ.get('AIL_RANGE_BUDGET', 200000))   # statement/expression visits
_MAXREL = 16                # at most this many symbolic facts per symbol (dropping one is sound)
_DEPTH = 3


class _Abort(Exception):
    pass


def _clip(lo, hi):
    return max(lo, MIN), min(hi, MAX)


def _norm(fact):
    lo, hi, ub, lb = fact
    if len(ub) > _MAXREL:
        ub = dict(sorted(ub.items())[:_MAXREL])
    if len(lb) > _MAXREL:
        lb = dict(sorted(lb.items())[:_MAXREL])
    return (lo, hi, ub, lb)


class Proofs:
    def __init__(self):
        self.noovf = {}      # id(node) -> bool (AND over recorded visits)
        self.inbounds = {}

    def ok_arith(self, node):
        return self.noovf.get(id(node), False)

    def ok_index(self, node):
        return self.inbounds.get(id(node), False)


class Info:
    """What the analysis needs from the compiler.

    kind(name) -> 'int' | 'list' | 'flist' | 'bytes' | 'bytearray' | None (None: not reasoned
    about); const(name) -> int value of a module constant or None; shadowed: names that are user
    functions or classes (a user `len` is not the built-in). field(owner, attr) -> the field's
    kind or None; fields(owner) -> every field kind of a class instance, or None; method(owner,
    attr) -> the method's original FunctionDef, or None."""

    def __init__(self, kind, const=lambda name: None, shadowed=frozenset(),
                 field=lambda owner, attr: None, fields=lambda owner: None,
                 method=lambda owner, attr: None):
        self.kind = kind
        self.const = const
        self.shadowed = shadowed
        self.field = field
        self.fields = fields
        self.method = method


def analyze(fn, info):
    proofs = Proofs()
    started = time.perf_counter()
    outcome = 'ok'
    try:
        _Analyzer(fn, info, proofs).run()
    except (_Abort, RecursionError) as error:
        proofs = Proofs()
        outcome = 'gave up: %s' % (error.args[0] if error.args else type(error).__name__)
    if os.environ.get('AIL_RANGE_TIME'):
        with open(os.environ['AIL_RANGE_TIME'], 'a') as out:
            out.write('%s %.4f %s\n' % (fn.name, time.perf_counter() - started, outcome))
    return proofs


def _loop_exits(node):
    """(has break, has continue) that leave the loop enclosing `node` (not one nested in it)."""
    brk = cont = False
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Break):
            brk = True
        elif isinstance(n, ast.Continue):
            cont = True
        elif isinstance(n, (ast.For, ast.While, ast.AsyncFor)) and n is not node:
            stack.extend(n.orelse)                      # only the else clause belongs to the outer loop
            continue
        if isinstance(n, (ast.For, ast.While, ast.AsyncFor)) and n is node:
            stack.extend(n.orelse)
            continue
        stack.extend(ast.iter_child_nodes(n))
    return brk, cont


def _names_stored(node):
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
    return out


class _Analyzer:
    def __init__(self, fn, info, proofs):
        self.fn = fn
        self.info = info
        self.proofs = proofs
        self.recording = True
        self.loops = []            # stack of [breaks, continues] state lists
        self.budget = _BUDGET
        self.kinds = {}
        self.loop_ids = {}
        self.stored_cache = {}
        self.tracked_objects = set()
        self.field_kinds = {}
        self.inline_returns = []

    # ---- setup ----
    def kind(self, name):
        if name not in self.kinds:
            try:
                k = self.info.kind(name)
            except Exception:
                k = None
            self.kinds[name] = k
        return self.kinds[name]

    def _trackable_objects(self):
        """The single object parameter whose every use is `name.field` or `name.method(...)`:
        a receiver that cannot be aliased by another name or parameter of this function. A
        second parameter could be the same object, so a function with any other parameter is
        never tracked. Only a tracked receiver may carry field facts."""
        a = self.fn.args
        if a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg or len(a.args) != 1:
            return set()
        name = a.args[0].arg
        try:
            fields = self.info.fields(name)
        except Exception:
            fields = None
        if os.environ.get('AIL_RANGE_DEBUG_INLINE'):
            print('track', name, fields, file=sys.stderr)
        if not fields or any(k not in ('int', 'bytes') for k in fields.values()):
            return set()
        cands = {name}
        parent = {}
        for p in ast.walk(self.fn):
            for c in ast.iter_child_nodes(p):
                parent[id(c)] = p
        for n in ast.walk(self.fn):
            if isinstance(n, ast.Name) and n.id in cands:
                p = parent.get(id(n))
                if not (isinstance(p, ast.Attribute) and p.value is n):
                    cands.discard(n.id)
        for lam in ast.walk(self.fn):
            if isinstance(lam, ast.Lambda):
                cands -= {n.id for n in ast.walk(lam) if isinstance(n, ast.Name)}
        return cands

    def field_kind(self, owner, attr):
        key = (owner, attr)
        if key not in self.field_kinds:
            try:
                k = self.info.field(owner, attr)
            except Exception:
                k = None
            self.field_kinds[key] = k
        return self.field_kinds[key]

    @staticmethod
    def field_sym(owner, attr):
        return '#fld:%s.%s' % (owner, attr)

    @staticmethod
    def field_len_sym(owner, attr):
        return '#len:#fld:%s.%s' % (owner, attr)

    def object_field_syms(self, owner):
        try:
            fields = self.info.fields(owner) or ()
        except Exception:
            fields = ()
        for attr in fields:
            yield self.field_sym(owner, attr)
            yield self.field_len_sym(owner, attr)

    def drop_fields(self, S, owner):
        for sym in self.object_field_syms(owner):
            self.drop_refs(S, sym)
            self.drop_markers(S, (sym,))

    def drop_markers(self, S, names):
        """Forget difference facts whose operands are about to change."""
        for key in list(S):
            if key.startswith('#sub|'):
                parts = key.split('|')
                if len(parts) == 5 and (parts[1] in names or parts[2] in names):
                    self.drop_refs(S, key)

    def inline_candidate(self, fn):
        """A zero-argument method whose body is only guards and a return, with no assignment,
        loop, try, nested definition or call outside the pure builtins. Such a body can be run
        against the caller's field facts; nothing it does can change the caller's state except
        the branch facts its own guard proves."""
        if not isinstance(fn, ast.FunctionDef):
            return False
        a = fn.args
        if (a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg or a.defaults
                or len(a.args) != 1 or a.args[0].arg != 'self'):
            return False
        if os.environ.get('AIL_RANGE_DEBUG_INLINE'):
            print('inline?', fn.name, file=sys.stderr)
        if len(fn.body) > 12:
            return False
        pure = ('len', 'ord', 'bool', 'abs', 'min', 'max')
        exceptions = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Raise) and n.exc is not None:
                exc = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
                if isinstance(exc, ast.Name) and exc.id not in self.info.shadowed:
                    exceptions.add(exc.id)
        allowed = {'self'} | exceptions
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id in pure and n.func.id not in self.info.shadowed \
                    and not n.keywords:
                allowed.add(n.func.id)
        for n in ast.walk(fn):
            if n is fn:
                continue
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For, ast.AsyncFor,
                              ast.While, ast.Try, ast.With, ast.AsyncWith, ast.FunctionDef,
                              ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda, ast.Yield,
                              ast.YieldFrom, ast.Await, ast.Global, ast.Nonlocal, ast.Delete,
                              ast.NamedExpr, ast.comprehension)):
                return False
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                return False
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in allowed:
                return False
            if isinstance(n, ast.Attribute) and isinstance(n.ctx, (ast.Store, ast.Del)):
                return False
            if isinstance(n, ast.Call):
                if not (isinstance(n.func, ast.Name)
                        and (n.func.id in pure or n.func.id in exceptions)
                        and n.func.id not in self.info.shadowed and not n.keywords):
                    return False
            if isinstance(n, ast.stmt) and not isinstance(n, (ast.If, ast.Raise, ast.Return,
                                                              ast.Pass, ast.Expr)):
                return False
        return True

    def run(self):
        fn = self.fn
        # A lambda cannot rebind this function's names (no `nonlocal` in a lambda) but may be
        # called at any time, so lists it mentions are never tracked; a nested def may rebind.
        for n in ast.walk(fn):
            if n is not fn and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                              ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom, ast.Await)):
                raise _Abort("nested definition or generator")
        self.tracked_lists = self._trackable_lists()
        self.tracked_objects = self._trackable_objects()
        # Element ranges of tracked int lists: every value such a list ever holds is stored by a
        # statement of this function (it is never aliased), so the union of the stored values'
        # ranges bounds every element read. Found by re-running the analysis until that union is
        # stable; only the final run's proofs are kept.
        self.elem = {x: None for x in self.tracked_lists if self.kind(x) == 'list'}
        for round_ in range(7):
            if round_ == 6:                         # not settled: every element may be anything
                self.elem = {x: (MIN, MAX) for x in self.elem}
            self.stored = {x: None for x in self.elem}
            self.loop_memo = {}                     # element ranges changed: loops must re-run
            self.proofs.noovf.clear()
            self.proofs.inbounds.clear()
            self.exec_block(fn.body, {})
            new = {}
            for x, old in self.elem.items():
                got = self.stored[x]
                if got is None:
                    new[x] = old
                elif old is None:
                    new[x] = got
                elif round_ >= 2:
                    new[x] = (old[0] if got[0] >= old[0] else MIN, old[1] if got[1] <= old[1] else MAX)
                else:
                    new[x] = (min(old[0], got[0]), max(old[1], got[1]))
            if new == self.elem:
                return
            self.elem = new
        raise _Abort("element ranges did not settle")

    def store_elem(self, name, val):
        """A value stored into list `name` (an element-range input)."""
        if name not in self.elem:
            return
        lo, hi = val[0], val[1]
        if lo > hi:
            return
        old = self.stored[name]
        self.stored[name] = (lo, hi) if old is None else (min(old[0], lo), max(old[1], hi))

    def opaque(self, node):
        """`node` is not analysed: any tracked list it may add values to holds anything."""
        for n in ast.walk(node):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and isinstance(n.func.value, ast.Name) and n.func.value.id in self.elem:
                self.store_elem(n.func.value.id, TOP)
            elif isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id in self.elem \
                    and not isinstance(n.ctx, ast.Load):
                self.store_elem(n.value.id, TOP)
            elif isinstance(n, ast.Name) and n.id in self.elem and not isinstance(n.ctx, ast.Load):
                self.store_elem(n.id, TOP)

    def _trackable_lists(self):
        """List/float-list locals that can never be aliased (see the module docstring)."""
        cands = {}
        params = {a.arg for a in self.fn.args.args}
        for n in ast.walk(self.fn):
            if isinstance(n, ast.Name) and self.kind(n.id) in ('list', 'flist') and n.id not in params:
                cands[n.id] = True
        if not cands:
            return set()
        ok = set(cands)
        for lam in ast.walk(self.fn):
            if isinstance(lam, ast.Lambda):
                ok -= {n.id for n in ast.walk(lam) if isinstance(n, ast.Name)}
        parents = {}
        for p in ast.walk(self.fn):
            for c in ast.iter_child_nodes(p):
                parents[id(c)] = p
        for n in ast.walk(self.fn):
            if not (isinstance(n, ast.Name) and n.id in ok):
                continue
            p = parents.get(id(n))
            if isinstance(n.ctx, ast.Store):
                # every binding must be a plain `X = <fresh list>` (or `X = Y`, which copies)
                if isinstance(p, (ast.Assign, ast.AnnAssign)) and (
                        (isinstance(p, ast.Assign) and len(p.targets) == 1 and p.targets[0] is n)
                        or (isinstance(p, ast.AnnAssign) and p.target is n)) \
                        and p.value is not None and (self._fresh_list(p.value) or self._list_copy(n, p.value)):
                    continue
                ok.discard(n.id)
                continue
            if isinstance(p, (ast.Assign, ast.AnnAssign)) and p.value is n:
                target = p.targets[0] if isinstance(p, ast.Assign) and len(p.targets) == 1 else \
                    p.target if isinstance(p, ast.AnnAssign) else None
                if isinstance(target, ast.Name) and self._list_copy(target, n):
                    continue                                # `Z = X` copies X (pyfunc `_assign`)
            if isinstance(n.ctx, ast.Del):
                ok.discard(n.id)
                continue
            if isinstance(p, ast.Subscript) and p.value is n and not isinstance(p.ctx, ast.Del) \
                    and not (isinstance(p.slice, ast.Slice) and isinstance(p.ctx, ast.Store)):
                continue                                    # X[i], X[a:b] (read), X[i] = v
            if isinstance(p, ast.Attribute) and p.value is n and isinstance(parents.get(id(p)), ast.Call) \
                    and parents[id(p)].func is p:
                continue                                    # X.method(...): resizes in place at most
            if isinstance(p, (ast.For, ast.comprehension)) and p.iter is n:
                continue
            if isinstance(p, ast.Compare) and any(isinstance(op, (ast.In, ast.NotIn)) for op in p.ops) \
                    and n is not p.left:
                continue
            if isinstance(p, ast.Call) and n in p.args and isinstance(p.func, ast.Name) \
                    and p.func.id in ('len', 'sum', 'min', 'max', 'sorted', 'print', 'str') \
                    and p.func.id not in self.info.shadowed:
                continue
            ok.discard(n.id)
        return ok

    def _list_copy(self, target, value):
        """`target = value` between two plain local lists of one kind: the compiler gives the target
        its own copy of the buffer (pyfunc `_assign`, SEMANTICS.md section 5a), never an alias."""
        params = {a.arg for a in self.fn.args.args}
        return (isinstance(value, ast.Name) and isinstance(target, ast.Name)
                and self.kind(value.id) == 'list' and self.kind(target.id) == 'list'
                and value.id not in params and target.id not in params)

    def _fresh_list(self, e):
        if isinstance(e, (ast.List, ast.ListComp)):
            return True
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mult) and (
                isinstance(e.left, ast.List) or isinstance(e.right, ast.List)):
            return True
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in ('list', 'sorted') \
                and e.func.id not in self.info.shadowed:
            return True
        return False

    # ---- recording ----
    def note(self, table, node, ok):
        if not self.recording:
            return
        key = id(node)
        table[key] = table.get(key, True) and bool(ok)

    def tick(self):
        self.budget -= 1
        if self.budget < 0:
            raise _Abort("budget")

    # ---- symbols ----
    def is_int(self, name):
        return self.kind(name) == 'int'

    def len_sym(self, name):
        k = self.kind(name)
        if k == 'bytes' or (k in ('list', 'flist') and name in self.tracked_lists):
            return '#len:' + name
        return None

    @staticmethod
    def fact(S, sym):
        return S.get(sym, TOP)

    def eff_hi(self, S, sym, depth=1):
        lo, hi, ub, lb = S.get(sym, TOP)
        if depth > 0:
            for s, c in ub.items():
                h = self.eff_hi(S, s, depth - 1) + c
                if h < hi:
                    hi = h
        return hi

    def eff_lo(self, S, sym, depth=1):
        lo, hi, ub, lb = S.get(sym, TOP)
        if depth > 0:
            for s, c in lb.items():
                l = self.eff_lo(S, s, depth - 1) + c
                if l > lo:
                    lo = l
        return lo

    def sym_val(self, S, sym):
        lo, hi, ub, lb = S.get(sym, TOP)
        ub = dict(ub); lb = dict(lb)
        ub[sym] = 0; lb[sym] = 0
        lo = max(lo, self.eff_lo(S, sym)); hi = min(hi, self.eff_hi(S, sym))
        if sym.startswith('#len:'):
            lo = max(lo, 0); hi = min(hi, LENMAX)
        return (lo, hi, ub, lb)

    # ---- state edits ----
    @staticmethod
    def drop_refs(S, sym):
        """Forget every fact that mentions `sym` (its own facts included)."""
        S.pop(sym, None)
        for k, (lo, hi, ub, lb) in list(S.items()):
            if sym in ub or sym in lb:
                ub = {s: c for s, c in ub.items() if s != sym}
                lb = {s: c for s, c in lb.items() if s != sym}
                S[k] = (lo, hi, ub, lb)

    @staticmethod
    def shift_refs(S, sym, k):
        """`sym` becomes sym + k: x <= sym_old + c is x <= sym_new + (c - k)."""
        for key, (lo, hi, ub, lb) in list(S.items()):
            if key == sym:
                continue
            if sym in ub or sym in lb:
                ub = dict(ub); lb = dict(lb)
                if sym in ub:
                    ub[sym] -= k
                if sym in lb:
                    lb[sym] -= k
                S[key] = (lo, hi, ub, lb)

    def set_sym(self, S, sym, val):
        """Bind `sym` to an abstract value computed in S (which must not mention sym) and add the
        reverse edges so queries can walk in either direction."""
        lo, hi, ub, lb = val
        lo, hi = _clip(lo, hi)
        ub = {s: c for s, c in ub.items() if s != sym and self.tracked_sym(s)}
        lb = {s: c for s, c in lb.items() if s != sym and self.tracked_sym(s)}
        f = _norm((lo, hi, ub, lb))
        if f == TOP:
            S.pop(sym, None)
        else:
            S[sym] = f
        for s, c in f[2].items():                       # sym <= s + c  =>  s >= sym - c
            self.add_lb(S, s, sym, -c)
        for s, c in f[3].items():                       # sym >= s + c  =>  s <= sym - c
            self.add_ub(S, s, sym, -c)

    def tracked_sym(self, s):
        return s.startswith('#') or self.is_int(s)

    @staticmethod
    def add_ub(S, sym, other, c):
        lo, hi, ub, lb = S.get(sym, TOP)
        if other in ub and ub[other] <= c:
            return
        ub = dict(ub); ub[other] = c
        S[sym] = _norm((lo, hi, ub, lb))

    @staticmethod
    def add_lb(S, sym, other, c):
        lo, hi, ub, lb = S.get(sym, TOP)
        if other in lb and lb[other] >= c:
            return
        lb = dict(lb); lb[other] = c
        S[sym] = _norm((lo, hi, ub, lb))

    @staticmethod
    def set_bounds(S, sym, lo=None, hi=None):
        flo, fhi, ub, lb = S.get(sym, TOP)
        if lo is not None and lo > flo:
            flo = lo
        if hi is not None and hi < fhi:
            fhi = hi
        S[sym] = (flo, fhi, ub, lb)
        return flo <= fhi

    def assign(self, S, name, val):
        """S is modified in place. `val` was computed in S before the assignment."""
        if not self.is_int(name):
            return
        self.drop_markers(S, (name,))
        lo, hi, ub, lb = val
        ub = {s: c for s, c in ub.items()
              if not (s.startswith('#sub|') and name in s.split('|')[1:3])}
        lb = {s: c for s, c in lb.items()
              if not (s.startswith('#sub|') and name in s.split('|')[1:3])}
        k = ub.get(name)
        if k is not None and lb.get(name) == k:
            # name = name + k: shift the facts of everything that mentions the old value
            old = S.get(name, TOP)
            self.shift_refs(S, name, k)
            nlo, nhi = _clip(old[0] + k, old[1] + k)
            nub = {s: c + k for s, c in old[2].items()}
            nlb = {s: c + k for s, c in old[3].items()}
            nlo = max(nlo, lo); nhi = min(nhi, hi)
            for s, c in ub.items():
                if s != name and (s not in nub or c < nub[s]):
                    nub[s] = c
            for s, c in lb.items():
                if s != name and (s not in nlb or c > nlb[s]):
                    nlb[s] = c
            S.pop(name, None)
            self.set_sym(S, name, (nlo, nhi, nub, nlb))
            return
        self.drop_refs(S, name)
        self.set_sym(S, name, val)

    def kill(self, S, names):
        for name in names:
            if self.is_int(name):
                self.drop_refs(S, name)
                self.drop_markers(S, (name,))
            ls = self.len_sym(name)
            if ls:
                self.drop_refs(S, ls)
                self.drop_markers(S, (ls,))
            if name in self.tracked_objects:
                self.drop_fields(S, name)

    # ---- joins ----
    def join(self, a, b):
        """Facts true in both states. A symbolic bound known on one side only survives when the
        other side's numeric bounds imply it there (`ri = 0` joined with `ri <= n - 1` keeps
        ri <= n - 1 when n >= 1 on the `ri = 0` side)."""
        if a is None:
            return None if b is None else dict(b)
        if b is None:
            return dict(a)
        out = {}
        for k, fa in a.items():
            fb = b.get(k)
            if fb is None:
                continue
            if fa is fb or fa == fb:
                out[k] = fa
                continue
            ub, lb = {}, {}
            for s in set(fa[2]) | set(fb[2]):
                ca, cb = fa[2].get(s), fb[2].get(s)
                if ca is None and self.eff_hi(a, k) - self.eff_lo(a, s) <= cb:
                    ca = cb
                if cb is None and self.eff_hi(b, k) - self.eff_lo(b, s) <= ca:
                    cb = ca
                if ca is not None and cb is not None:
                    ub[s] = max(ca, cb)
            for s in set(fa[3]) | set(fb[3]):
                ca, cb = fa[3].get(s), fb[3].get(s)
                if ca is None and self.eff_lo(a, k) - self.eff_hi(a, s) >= cb:
                    ca = cb
                if cb is None and self.eff_lo(b, k) - self.eff_hi(b, s) >= ca:
                    cb = ca
                if ca is not None and cb is not None:
                    lb[s] = min(ca, cb)
            f = _norm((min(fa[0], fb[0]), max(fa[1], fb[1]), ub, lb))
            if f != TOP:
                out[k] = f
        return out

    @staticmethod
    def widen(old, new):
        if old is None:
            return new
        if new is None:
            return old
        out = {}
        for k, fo in old.items():
            fn = new.get(k)
            if fn is None:
                continue
            lo = fo[0] if fn[0] >= fo[0] else MIN
            hi = fo[1] if fn[1] <= fo[1] else MAX
            ub = {s: c for s, c in fo[2].items() if s in fn[2] and fn[2][s] <= c}
            lb = {s: c for s, c in fo[3].items() if s in fn[3] and fn[3][s] >= c}
            f = (lo, hi, ub, lb)
            if f != TOP:
                out[k] = f
        return out

    # ---- expressions ----
    def stored_in_expr(self, e):
        """Names an expression itself may bind (walrus, comprehension variables) and tracked lists
        whose length it may change (method calls on them)."""
        cached = self.stored_cache.get(id(e))
        if cached is not None:
            return cached
        names, lists = set(), set()
        self.stored_cache[id(e)] = (names, lists)       # the AST is alive (and unchanged) throughout
        for n in ast.walk(e):
            if isinstance(n, ast.NamedExpr):
                names |= _names_stored(n.target)
            elif isinstance(n, ast.comprehension):
                names |= _names_stored(n.target)
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and isinstance(n.func.value, ast.Name) and self.kind(n.func.value.id) in ('list', 'flist'):
                lists.add(n.func.value.id)
        return names, lists

    def pre_kill(self, S, exprs):
        names, lists = set(), set()
        for e in exprs:
            if e is not None:
                a, b = self.stored_in_expr(e)
                names |= a; lists |= b
        self.kill(S, names)
        for x in lists:
            ls = self.len_sym(x)
            if ls:
                self.drop_refs(S, ls)
            if x in self.tracked_objects:
                self.drop_fields(S, x)

    def ev(self, e, S):
        """Abstract value of e in state S; records proofs for nodes inside e."""
        self.tick()
        if isinstance(e, ast.Constant):
            v = e.value
            if isinstance(v, bool):
                return (int(v), int(v), {}, {})
            if isinstance(v, int):
                return (v, v, {}, {})
            return TOP
        if isinstance(e, ast.Name):
            if self.is_int(e.id):
                return self.sym_val(S, e.id)
            c = self.info.const(e.id)
            if isinstance(c, int) and not isinstance(c, bool):
                return (c, c, {}, {})
            return TOP
        if isinstance(e, ast.BinOp):
            a = self.ev(e.left, S)
            b = self.ev(e.right, S)
            val, ok = self.binop(e.op, a, b, S)
            if isinstance(e.op, _ARITH):
                self.note(self.proofs.noovf, e, ok)
            return val
        if isinstance(e, ast.UnaryOp):
            a = self.ev(e.operand, S)
            if isinstance(e.op, ast.Not):
                return (0, 1, {}, {})
            if isinstance(e.op, ast.UAdd):
                return a
            if isinstance(e.op, ast.USub):
                lo, hi = _clip(-a[1], -a[0])
                return (lo, hi, {}, {})
            if isinstance(e.op, ast.Invert):
                return (~a[1], ~a[0], {}, {})
            return TOP
        if isinstance(e, ast.Compare):
            self.ev(e.left, S)
            for c in e.comparators:
                self.ev(c, S)
            return (0, 1, {}, {})
        if isinstance(e, ast.BoolOp):
            cur = dict(S)
            vals = []
            for i, v in enumerate(e.values):
                if cur is None:
                    break
                vals.append(self.ev(v, cur))
                if i + 1 < len(e.values):
                    cur = self.refine(cur, v, isinstance(e.op, ast.And))
            lo = min(v[0] for v in vals); hi = max(v[1] for v in vals)
            return (lo, hi, {}, {})
        if isinstance(e, ast.IfExp):
            self.ev(e.test, S)
            t = self.refine(dict(S), e.test, True)
            f = self.refine(dict(S), e.test, False)
            vals = []
            if t is not None:
                vals.append(self.ev(e.body, t))
            if f is not None:
                vals.append(self.ev(e.orelse, f))
            if not vals:
                return TOP
            ub = {s: c for s, c in vals[0][2].items() if all(s in v[2] for v in vals)}
            ub = {s: max(v[2][s] for v in vals) for s in ub}
            lb = {s: c for s, c in vals[0][3].items() if all(s in v[3] for v in vals)}
            lb = {s: min(v[3][s] for v in vals) for s in lb}
            return (min(v[0] for v in vals), max(v[1] for v in vals), ub, lb)
        if isinstance(e, ast.Subscript):
            return self.subscript(e, S)
        if isinstance(e, ast.Call):
            return self.call(e, S)
        if isinstance(e, (ast.Tuple, ast.List, ast.Set)):
            for x in e.elts:
                self.ev(x, S)
            return TOP
        if isinstance(e, ast.Attribute):
            self.ev(e.value, S)
            if isinstance(e.value, ast.Name) and e.value.id in self.tracked_objects \
                    and self.field_kind(e.value.id, e.attr) == 'int':
                return self.sym_val(S, self.field_sym(e.value.id, e.attr))
            return TOP
        if isinstance(e, ast.Dict):
            for x in list(e.keys) + list(e.values):
                if x is not None:
                    self.ev(x, S)
            return TOP
        # comprehensions, f-strings, lambdas, starred, slices...: never descended into
        self.opaque(e)
        for n in ast.walk(e):
            if isinstance(n, ast.Name) and n.id in self.tracked_objects:
                self.drop_fields(S, n.id)
        return TOP

    def subscript(self, e, S):
        sl = e.slice
        base = e.value
        if isinstance(sl, ast.Slice):
            for x in (sl.lower, sl.upper, sl.step):
                if x is not None:
                    self.ev(x, S)
            if not isinstance(base, ast.Name):
                self.ev(base, S)
            return TOP
        idx = self.ev(sl, S)
        if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) \
                and base.value.id in self.tracked_objects:
            self.ev(base, S)
            owner, attr = base.value.id, base.attr
            fk = self.field_kind(owner, attr)
            if fk in ('list', 'flist', 'bytes'):
                ls = self.field_len_sym(owner, attr)
                ok = self.recording and idx[0] >= 0 and self.prove_le(S, idx, ls, -1)
                self.note(self.proofs.inbounds, e, ok)
            if fk in ('bytes', 'bytearray'):
                return (0, 255, {}, {})
            return TOP
        if not isinstance(base, ast.Name):
            self.ev(base, S)
            return TOP
        k = self.kind(base.id)
        ls = self.len_sym(base.id)
        if k in ('list', 'flist', 'bytes'):
            ok = self.recording and ls is not None and idx[0] >= 0 and self.prove_le(S, idx, ls, -1)
            self.note(self.proofs.inbounds, e, ok)
            if _DEBUG and self.recording and not ok:
                with open(os.environ['AIL_RANGE_DEBUG'], 'a') as dbg:
                    print('rangecheck: %s:%s %s idx=%r len=%r' % (getattr(e, 'lineno', '?'), ast.unparse(e), ls,
                          idx, S.get(ls) if ls else None), file=dbg)
        if k in ('bytes', 'bytearray'):
            return (0, 255, {}, {})
        return self.elem_val(base.id)

    def elem_val(self, name):
        r = self.elem.get(name)
        return TOP if r is None else (r[0], r[1], {}, {})

    def prove_le(self, S, val, target, k):
        """val <= target + k ?"""
        lo, hi, ub, lb = val
        if hi <= self.eff_lo(S, target) + k:
            return True
        best = {}
        for s, c in ub.items():
            if s == target and c <= k:
                return True
            best[s] = c
        frontier = dict(best)
        seen = set()
        for _ in range(_DEPTH):
            nxt = {}
            for s, c in frontier.items():
                if s in seen:
                    continue
                seen.add(s)
                for s2, c2 in S.get(s, TOP)[2].items():
                    cc = c + c2
                    if s2 == target and cc <= k:
                        return True
                    if s2 not in best or cc < best[s2]:
                        best[s2] = cc
                    if s2 not in seen and (s2 not in nxt or cc < nxt[s2]):
                        nxt[s2] = cc
                    if self.eff_hi(S, s2, 1) + cc <= self.eff_lo(S, target) + k:
                        return True
            if not nxt:
                break
            frontier = nxt
        return False

    def call(self, e, S):
        for a in e.args:
            self.ev(a, S)
        for kw in e.keywords:
            self.ev(kw.value, S)
        f = e.func
        tracked_call = (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                        and f.value.id in self.tracked_objects)
        pure_builtin = (isinstance(f, ast.Name) and f.id in
                        ('len', 'ord', 'bool', 'abs', 'min', 'max')
                        and f.id not in self.info.shadowed and not e.keywords)
        if not tracked_call and not pure_builtin:
            # A field handed to other code (or the receiver of a method on the field) may be
            # mutated there; the field facts must not survive that call.
            for n in ast.walk(e):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) \
                        and n.value.id in self.tracked_objects:
                    self.drop_fields(S, n.value.id)
        if isinstance(f, ast.Attribute):
            if not isinstance(f.value, ast.Name):
                self.ev(f.value, S)
                return TOP
            if f.value.id in self.elem:
                if f.attr == 'append' and len(e.args) == 1 and not e.keywords:
                    self.store_elem(f.value.id, self.peek(e.args[0], S))
                elif f.attr == 'insert' and len(e.args) == 2 and not e.keywords:
                    self.store_elem(f.value.id, self.peek(e.args[1], S))
                elif f.attr not in ('pop', 'sort', 'reverse', 'clear', 'index', 'count', 'copy', 'remove'):
                    self.store_elem(f.value.id, TOP)
                if f.attr == 'pop':
                    return self.elem_val(f.value.id)
            if f.value.id in self.tracked_objects:
                try:
                    callee = self.info.method(f.value.id, f.attr)
                except Exception:
                    callee = None
                if callee is not None and not e.args and not e.keywords \
                        and self.inline_candidate(callee):
                    saved = self.recording
                    self.recording = False
                    self.inline_returns.append([])
                    try:
                        out = self.exec_block(callee.body, dict(S))
                    finally:
                        rets = self.inline_returns.pop()
                        self.recording = saved
                    if out is None and len(rets) == 1:
                        retS, val = rets[0]
                        S.clear()
                        S.update(retS)
                        return val
                self.drop_fields(S, f.value.id)
                return TOP
            # only the built-in text/byte/list methods (a struct may define its own `find`)
            if self.kind(f.value.id) in ('str', 'bytes', 'bytearray') and not e.keywords:
                if f.attr in ('find', 'rfind'):
                    return (-1, LENMAX, {}, {})
                if f.attr == 'count':
                    return (0, LENMAX, {}, {})
            return TOP
        if not isinstance(f, ast.Name) or f.id in self.info.shadowed or e.keywords:
            return TOP
        name, args = f.id, e.args
        if name == 'len' and len(args) == 1:
            a = args[0]
            if isinstance(a, ast.Name):
                ls = self.len_sym(a.id)
                if ls:
                    return self.sym_val(S, ls)
                if self.kind(a.id) in ('list', 'flist', 'bytes', 'bytearray'):
                    return (0, LENMAX, {}, {})
            if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) \
                    and a.value.id in self.tracked_objects:
                fk = self.field_kind(a.value.id, a.attr)
                if fk in ('list', 'flist', 'bytes', 'bytearray'):
                    return self.sym_val(S, self.field_len_sym(a.value.id, a.attr))
                return TOP
            return (0, MAX, {}, {})
        if name == 'ord' and len(args) == 1:
            return (0, 0x10FFFF, {}, {})
        if name == 'bool' and len(args) == 1:
            return (0, 1, {}, {})
        if name == 'abs' and len(args) == 1:
            a = self.ev(args[0], S) if False else self.peek(args[0], S)
            m = max(abs(a[0]), abs(a[1]))
            return (0 if a[0] <= 0 <= a[1] else min(abs(a[0]), abs(a[1])), min(m, MAX), {}, {})
        if name in ('min', 'max') and len(args) >= 2:
            vals = [self.peek(a, S) for a in args]
            if name == 'min':
                lo = min(v[0] for v in vals); hi = min(v[1] for v in vals)
                ub = {}
                for v in vals:
                    for s, c in v[2].items():
                        if s not in ub or c < ub[s]:
                            ub[s] = c
                return (lo, hi, ub, {})
            lo = max(v[0] for v in vals); hi = max(v[1] for v in vals)
            lb = {}
            for v in vals:
                for s, c in v[3].items():
                    if s not in lb or c > lb[s]:
                        lb[s] = c
            return (lo, hi, {}, lb)
        return TOP

    def peek(self, e, S):
        """Value without recording (the node was already evaluated for proofs)."""
        saved = self.recording
        self.recording = False
        try:
            return self.ev(e, S)
        finally:
            self.recording = saved

    def binop(self, op, a, b, S):
        """(value, no-overflow) for a op b."""
        alo, ahi, aub, alb = a
        blo, bhi, bub, blb = b
        if isinstance(op, ast.Add):
            lo, hi = alo + blo, ahi + bhi
            ub, lb = {}, {}
            if abs(bhi) <= LENMAX:
                ub.update({s: c + bhi for s, c in aub.items()})
            if abs(blo) <= LENMAX:
                lb.update({s: c + blo for s, c in alb.items()})
            if abs(ahi) <= LENMAX:
                for s, c in bub.items():
                    if s not in ub or c + ahi < ub[s]:
                        ub[s] = c + ahi
            if abs(alo) <= LENMAX:
                for s, c in blb.items():
                    if s not in lb or c + alo > lb[s]:
                        lb[s] = c + alo
            # a <= s + c with s <= MAX and b <= -c  =>  a + b <= MAX (and the mirror image)
            for s, c in aub.items():
                hi = min(hi, self.eff_hi(S, s) + c + bhi)
            for s, c in bub.items():
                hi = min(hi, self.eff_hi(S, s) + c + ahi)
            for s, c in alb.items():
                lo = max(lo, self.eff_lo(S, s) + c + blo)
            for s, c in blb.items():
                lo = max(lo, self.eff_lo(S, s) + c + alo)
        elif isinstance(op, ast.Sub):
            lo, hi = alo - bhi, ahi - blo
            ub, lb = {}, {}
            if abs(blo) <= LENMAX:
                ub.update({s: c - blo for s, c in aub.items()})
            if abs(bhi) <= LENMAX:
                lb.update({s: c - bhi for s, c in alb.items()})
            for s, c in aub.items():
                hi = min(hi, self.eff_hi(S, s) + c - blo)
            for s, c in alb.items():
                lo = max(lo, self.eff_lo(S, s) + c - bhi)
            # shared symbol: a >= s + d, b <= s + c  =>  a - b >= d - c ; a <= s + d, b >= s + c => a - b <= d - c
            for s, d in alb.items():
                if s in bub:
                    lo = max(lo, d - bub[s])
            for s, d in aub.items():
                if s in blb:
                    hi = min(hi, d - blb[s])
            ea, eb = self.exact_syms(a), self.exact_syms(b)
            if len(ea) == 1 and len(eb) == 1:
                # Keep the identity `result == (sa + oa) - (sb + ob)` so a guard on the result
                # (`available < n`) can refine the operands themselves (`position <= len - n`).
                marker = '#sub|%s|%s|%d|%d' % (ea[0][0], eb[0][0], ea[0][1], eb[0][1])
                ub[marker] = 0
                lb[marker] = 0
        elif isinstance(op, ast.Mult):
            ps = (alo * blo, alo * bhi, ahi * blo, ahi * bhi)
            lo, hi = min(ps), max(ps)
            ub, lb = {}, {}
            if blo == bhi == 1:
                ub, lb = dict(aub), dict(alb)
            elif alo == ahi == 1:
                ub, lb = dict(bub), dict(blb)
        elif isinstance(op, ast.Mod):
            if blo >= 1:
                lo, hi = 0, bhi - 1
                if alo >= 0:
                    hi = min(hi, ahi)
                ub = {s: c - 1 for s, c in bub.items()}
                if alo >= 0 and ahi < blo:            # x % m == x
                    return (alo, ahi, dict(aub), dict(alb)), True
                return (lo, hi, ub, {}), True
            if bhi <= -1:
                return (blo + 1, 0, {}, {}), True
            return TOP, False
        elif isinstance(op, ast.FloorDiv):
            if blo >= 1 or bhi <= -1:
                ps = [x // y for x in (alo, ahi) for y in (blo, bhi)]
                lo, hi = _clip(min(ps), max(ps))       # MIN // -1 raises
                return (lo, hi, {}, {}), True
            if alo >= 0 and blo >= 0:
                return (0, ahi, {}, {}), True
            return TOP, False
        elif isinstance(op, ast.BitAnd):
            # x & m with m >= 0 is in [0, m] (its bits are a subset of m's), so it is also below
            # every symbolic upper bound of m: `key & mask` with mask == len(cnt) - 1 indexes cnt
            if alo >= 0 and blo >= 0:
                ub = dict(bub)
                for s, c in aub.items():
                    if s not in ub or c < ub[s]:
                        ub[s] = c
                return (0, min(ahi, bhi), ub, {}), True
            if alo >= 0:
                return (0, ahi, dict(aub), {}), True
            if blo >= 0:
                return (0, bhi, dict(bub), {}), True
            return TOP, False
        elif isinstance(op, (ast.BitOr, ast.BitXor)):
            if alo >= 0 and blo >= 0:
                return (0, (1 << max(ahi, bhi).bit_length()) - 1, {}, {}), True
            return TOP, False
        elif isinstance(op, ast.LShift):
            if blo == bhi and 0 <= blo < 64:            # a shift that leaves int64 raises
                lo, hi = _clip(alo << blo, ahi << blo)
                return (lo, hi, {}, {}), True
            if alo >= 0:                                # a negative count raises: a << s >= a >= 0
                return (alo, MAX, {}, {}), True
            return TOP, False
        elif isinstance(op, ast.RShift):
            if blo == bhi and 0 <= blo < 64:
                return (alo >> blo, ahi >> blo, {}, {}), True
            if blo >= 0 and alo >= 0:
                return (0, ahi, {}, {}), True
            return TOP, False
        else:
            return TOP, False
        ok = MIN <= lo and hi <= MAX
        lo, hi = _clip(lo, hi)
        return (lo, hi, ub, lb), ok

    # ---- conditions ----
    def refine(self, S, test, truth):
        """S restricted to executions where `test` is `truth`; None when impossible. S is not
        modified."""
        if S is None:
            return None
        self.tick()
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            return self.refine(S, test.operand, not truth)
        if isinstance(test, ast.Constant):
            return S if bool(test.value) == truth else None
        if isinstance(test, ast.BoolOp):
            conj = isinstance(test.op, ast.And) == truth
            if conj:                                    # every operand has the value `truth`
                cur = S
                for v in test.values:
                    cur = self.refine(cur, v, truth)
                    if cur is None:
                        return None
                return cur
            out, cur = None, S                          # some operand decides
            for v in test.values:
                if cur is None:
                    break
                out = self.join(out, self.refine(cur, v, truth)) if out is not None else self.refine(cur, v, truth)
                cur = self.refine(cur, v, not truth)
            return out
        if isinstance(test, ast.Compare):
            cur = S
            left = test.left
            if not truth and len(test.ops) > 1:
                return S                                # a negated chain: no single fact
            for op, right in zip(test.ops, test.comparators):
                cur = self.refine_cmp(cur, left, op, right, truth)
                if cur is None:
                    return None
                left = right
            return cur
        return S

    _NEG = {ast.Lt: ast.GtE, ast.LtE: ast.Gt, ast.Gt: ast.LtE, ast.GtE: ast.Lt, ast.Eq: ast.NotEq,
            ast.NotEq: ast.Eq}

    def refine_cmp(self, S, left, op, right, truth):
        t = type(op)
        if t not in self._NEG:
            return S
        if not truth:
            t = self._NEG[t]
        if not (self.int_expr(left) and self.int_expr(right)):
            return S                    # a float or text comparison says nothing about int bounds
        a = self.peek(left, S)
        b = self.peek(right, S)
        S = dict(S)
        marker = self.sub_marker(a)
        if marker is not None and b[0] == b[1] and t is not ast.NotEq:
            _, sa, sb, oa, ob = marker.split('|')
            d = b[0] - int(oa) + int(ob)
            if t is ast.Lt:
                self.add_lb(S, sb, sa, -(d - 1))
                self.add_ub(S, sa, sb, d - 1)
            elif t is ast.LtE:
                self.add_lb(S, sb, sa, -d)
                self.add_ub(S, sa, sb, d)
            elif t is ast.Gt:
                self.add_ub(S, sb, sa, -(d + 1))
                self.add_lb(S, sa, sb, d + 1)
            elif t is ast.GtE:
                self.add_ub(S, sb, sa, -d)
                self.add_lb(S, sa, sb, d)
            elif t is ast.Eq:
                self.add_lb(S, sb, sa, -d)
                self.add_ub(S, sa, sb, d)
                self.add_ub(S, sb, sa, -d)
                self.add_lb(S, sa, sb, d)
            return S
        if t is ast.Lt:
            ok = self.le(S, left, a, right, b, -1)
        elif t is ast.LtE:
            ok = self.le(S, left, a, right, b, 0)
        elif t is ast.Gt:
            ok = self.le(S, right, b, left, a, -1)
        elif t is ast.GtE:
            ok = self.le(S, right, b, left, a, 0)
        elif t is ast.Eq:
            ok = self.le(S, left, a, right, b, 0) and self.le(S, right, b, left, a, 0)
        else:
            ok = self.ne(S, a, b)
        return S if ok else None

    def int_expr(self, e):
        """Is `e` certainly an int (or bool) value? Only then do its bounds mean anything."""
        if isinstance(e, ast.Constant):
            return isinstance(e.value, int)
        if isinstance(e, ast.Name):
            c = self.info.const(e.id)
            return self.is_int(e.id) or (isinstance(c, int) and not isinstance(c, bool))
        if isinstance(e, ast.BinOp):
            return not isinstance(e.op, (ast.Div, ast.Pow, ast.MatMult)) \
                and self.int_expr(e.left) and self.int_expr(e.right)
        if isinstance(e, ast.UnaryOp):
            return isinstance(e.op, ast.Not) or self.int_expr(e.operand)
        if isinstance(e, ast.Compare):
            return True
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id not in self.info.shadowed \
                and not e.keywords:
            if e.func.id in ('len', 'ord', 'bool'):
                return True
            if e.func.id in ('abs', 'min', 'max') and e.args:
                return all(self.int_expr(a) for a in e.args)
            return False
        if isinstance(e, ast.Subscript) and not isinstance(e.slice, ast.Slice) and isinstance(e.value, ast.Name):
            return self.kind(e.value.id) in ('bytes', 'bytearray', 'list')
        if isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) \
                and e.value.id in self.tracked_objects:
            return self.field_kind(e.value.id, e.attr) == 'int'
        return False

    def exact_syms(self, val):
        return [(s, c) for s, c in val[2].items() if val[3].get(s) == c]

    @staticmethod
    def sub_marker(val):
        for s, c in val[2].items():
            if s.startswith('#sub|') and c == 0 and val[3].get(s) == 0:
                return s
        return None

    def le(self, S, le, a, re, b, k):
        """Add a <= b + k to S (in place). False when that is impossible."""
        if a[0] > b[1] + k:
            return False
        for s, off in self.exact_syms(a):               # a == s + off  =>  s <= b + k - off
            if not self.set_bounds(S, s, hi=b[1] + k - off):
                return False
            for t, c in b[2].items():
                if t != s:
                    self.add_ub(S, s, t, c + k - off)
                    self.add_lb(S, t, s, -(c + k - off))
        for s, off in self.exact_syms(b):               # b == s + off  =>  s >= a - k - off
            if not self.set_bounds(S, s, lo=a[0] - k - off):
                return False
            for t, c in a[3].items():
                if t != s:
                    self.add_lb(S, s, t, c - k - off)
                    self.add_ub(S, t, s, -(c - k - off))
        return True

    def ne(self, S, a, b):
        ea, eb = self.exact_syms(a), self.exact_syms(b)
        if a[0] == a[1] and b[0] == b[1]:
            return a[0] != b[0]
        if b[0] == b[1]:
            for s, off in ea:
                lo, hi, ub, lb = S.get(s, TOP)
                v = b[0] - off
                if lo == v:
                    lo += 1
                if hi == v:
                    hi -= 1
                if lo > hi:
                    return False
                S[s] = (lo, hi, ub, lb)
        if a[0] == a[1]:
            return self.ne(S, b, a)
        for s, off in ea:
            for t, c in eb:
                # s + off != t + c, i.e. s != t + (c - off)
                d = c - off
                lo, hi, ub, lb = S.get(s, TOP)
                if ub.get(t) == d:
                    self.add_ub(S, s, t, d - 1); self.add_lb(S, t, s, 1 - d)
                if lb.get(t) == d:
                    self.add_lb(S, s, t, d + 1); self.add_ub(S, t, s, -d - 1)
        return True

    def resize_step(self, call):
        """+1 / -1 when `call` is X.append(v), X.insert(i, v) or X.pop([i]) on a tracked list X that
        the call's arguments do not mention (and that nothing in them can rebind); else None."""
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and not call.keywords):
            return None
        x = call.func.value.id
        if x not in self.tracked_lists:
            return None
        step = {'append': (1, 1), 'insert': (2, 1), 'pop': (None, -1)}.get(call.func.attr)
        if step is None or (step[0] is not None and len(call.args) != step[0]) \
                or (step[0] is None and len(call.args) > 1):
            return None
        for a in call.args:
            for n in ast.walk(a):
                if isinstance(n, ast.Name) and n.id == x or isinstance(n, (ast.NamedExpr, ast.comprehension,
                                                                            ast.Lambda)):
                    return None
        return step[1]

    def shift_sym(self, S, sym, k):
        """`sym` becomes sym + k (an exact step), keeping every relation that mentions it."""
        lo, hi, ub, lb = S.get(sym, TOP)
        self.shift_refs(S, sym, k)
        nlo, nhi = _clip(lo + k if lo > MIN else MIN, hi + k if hi < MAX else MAX)
        f = (nlo, nhi, {s: c + k for s, c in ub.items()}, {s: c + k for s, c in lb.items()})
        if f == TOP:
            S.pop(sym, None)
        else:
            S[sym] = f

    # ---- statements ----
    def exec_block(self, stmts, S):
        for st in stmts:
            if S is None:
                return None
            S = self.exec_stmt(st, S)
        return S

    def exec_stmt(self, st, S):
        self.tick()
        S = dict(S)
        if isinstance(st, ast.Expr):
            grow = self.resize_step(st.value)
            if grow is not None:
                # `X.append(v)` / `X.insert(i, v)` / `X.pop()` as a statement, X mentioned nowhere
                # else in it: every read in it sees the old length, and afterwards len(X) moved by
                # exactly one (pop on an empty list raises instead of returning).
                self.ev(st.value, S)
                self.shift_sym(S, '#len:' + st.value.func.value.id, grow)
                return S
            self.pre_kill(S, [st.value])
            self.ev(st.value, S)
            return S
        if isinstance(st, (ast.Assign, ast.AnnAssign)):
            targets = st.targets if isinstance(st, ast.Assign) else [st.target]
            if st.value is None:
                return S
            self.pre_kill(S, [st.value] + targets)
            if len(targets) == 1 and isinstance(targets[0], ast.Name):
                name = targets[0].id
                val = self.ev(st.value, S)
                if name in self.elem:
                    self.store_elem(name, self.fresh_elems(st.value, S))
                ls = self.len_sym(name)
                if ls:
                    lv = self.len_of_fresh(st.value, S) if self.kind(name) != 'bytes' else self.len_of_bytes(st.value, S)
                    self.drop_refs(S, ls)
                    if lv is not None:
                        self.set_sym(S, ls, lv)
                if self.is_int(name):
                    self.assign(S, name, val)
                elif not ls:
                    self.kill(S, [name])
                return S
            if len(targets) == 1 and isinstance(targets[0], ast.Tuple) and isinstance(st.value, ast.Tuple) \
                    and len(targets[0].elts) == len(st.value.elts) \
                    and all(isinstance(t, ast.Name) for t in targets[0].elts):
                names = [t.id for t in targets[0].elts]
                vals = [self.ev(v, S) for v in st.value.elts]
                self.kill(S, names)
                for n, v in zip(names, vals):
                    if self.is_int(n):
                        lo, hi, ub, lb = v
                        ub = {s: c for s, c in ub.items() if s not in names}
                        lb = {s: c for s, c in lb.items() if s not in names}
                        self.set_sym(S, n, (lo, hi, ub, lb))
                return S
            val = self.ev(st.value, S)
            for t in targets:
                self.target_store(t, S, val if len(targets) == 1 else TOP)
            return S
        if isinstance(st, ast.AugAssign):
            self.pre_kill(S, [st.value, st.target])
            if isinstance(st.target, ast.Name):
                name = st.target.id
                b = self.ev(st.value, S)
                if self.is_int(name):
                    a = self.sym_val(S, name)
                    val, ok = self.binop(st.op, a, b, S)
                    if isinstance(st.op, _ARITH):
                        self.note(self.proofs.noovf, st, ok)
                    self.assign(S, name, val)
                else:
                    self.kill(S, [name])
                return S
            b = self.ev(st.value, S)
            stored = TOP
            if isinstance(st.target, ast.Subscript) and isinstance(st.target.value, ast.Name) \
                    and st.target.value.id in self.elem:
                stored, _ = self.binop(st.op, self.elem_val(st.target.value.id), b, S)
            self.target_store(st.target, S, stored)
            return S
        if isinstance(st, ast.If):
            self.pre_kill(S, [st.test])
            self.ev(st.test, S)
            t = self.exec_block(st.body, self.refine(S, st.test, True))
            f = self.exec_block(st.orelse, self.refine(S, st.test, False))
            return self.join(t, f)
        if isinstance(st, (ast.While, ast.For)):
            # A loop statement is a function of its entry state (with the element ranges of this
            # round fixed): inside an enclosing loop's settling passes the same entry often comes
            # back, and nested loops would otherwise multiply the work. Recording passes always run.
            if not self.recording:
                hit = self.loop_memo.get(id(st))
                if hit is not None and hit[0] == S:
                    return dict(hit[1]) if hit[1] is not None else None
            entry = dict(S) if not self.recording else None
            out = self.exec_while(st, S) if isinstance(st, ast.While) else self.exec_for(st, S)
            if entry is not None:
                self.loop_memo[id(st)] = (entry, dict(out) if out is not None else None)
            return out
        if isinstance(st, ast.Break):
            if not self.loops:
                raise _Abort("break outside a loop")
            self.loops[-1][0].append(S)
            return None
        if isinstance(st, ast.Continue):
            if not self.loops:
                raise _Abort("continue outside a loop")
            self.loops[-1][1].append(S)
            return None
        if isinstance(st, ast.Return):
            val = TOP
            if st.value is not None:
                self.pre_kill(S, [st.value])
                val = self.ev(st.value, S)
            if self.inline_returns:
                self.inline_returns[-1].append((S, val))
            return None
        if isinstance(st, ast.Raise):
            return None
        if isinstance(st, ast.Pass):
            return S
        if isinstance(st, ast.Assert):
            self.pre_kill(S, [st.test])
            self.ev(st.test, S)
            return self.refine(S, st.test, True)
        if isinstance(st, ast.Try) or type(st).__name__ == 'TryStar':
            return self.exec_try(st, S)
        # anything else (with, del, match, ...): forget whatever it may assign; nothing inside is
        # marked. A break/continue inside leaves the loop in that forgotten state.
        self.forget(S, st)
        brk, cont = _loop_exits(st)
        if (brk or cont) and not self.loops:
            raise _Abort("break or continue outside a loop")
        if brk:
            self.loops[-1][0].append(dict(S))
        if cont:
            self.loops[-1][1].append(dict(S))
        return S

    def forget(self, S, node, unanalysed=True):
        if unanalysed:
            self.opaque(node)
        names = _names_stored(node)
        lists = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                lists.add(n.id)
        self.kill(S, names)
        for x in lists:
            ls = self.len_sym(x)
            if ls:
                self.drop_refs(S, ls)

    def target_store(self, t, S, val=TOP):
        """A store of `val` into something other than a plain int name."""
        if isinstance(t, ast.Name):
            self.kill(S, [t.id])
            self.opaque(t)
        elif isinstance(t, ast.Subscript):
            if isinstance(t.slice, ast.Slice):
                self.forget(S, t)
                return
            idx = self.ev(t.slice, S)
            if isinstance(t.value, ast.Name):
                self.store_elem(t.value.id, val)
                k = self.kind(t.value.id)
                ls = self.len_sym(t.value.id)
                if k in ('list', 'flist', 'bytes'):
                    ok = self.recording and ls is not None and idx[0] >= 0 and self.prove_le(S, idx, ls, -1)
                    self.note(self.proofs.inbounds, t, ok)
            else:
                self.ev(t.value, S)
        elif isinstance(t, ast.Attribute):
            self.ev(t.value, S)
            if isinstance(t.value, ast.Name) and t.value.id in self.tracked_objects:
                sym = self.field_sym(t.value.id, t.attr)
                self.drop_refs(S, sym)
                self.drop_markers(S, (sym,))
                if self.field_kind(t.value.id, t.attr) == 'int':
                    self.set_sym(S, sym, val)
                else:
                    ls = self.field_len_sym(t.value.id, t.attr)
                    self.drop_refs(S, ls)
                    self.drop_markers(S, (ls,))
        else:
            self.forget(S, t)

    def len_of_fresh(self, e, S):
        """Length of a fresh list expression, or None."""
        if isinstance(e, ast.Name):                     # a copy of another plain local list
            ls = self.len_sym(e.id)
            return self.sym_val(S, ls) if ls else (0, LENMAX, {}, {})
        if isinstance(e, ast.List):
            if any(isinstance(x, ast.Starred) for x in e.elts):
                return None
            n = len(e.elts)
            return (n, n, {}, {})
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mult):
            lit, cnt = (e.left, e.right) if isinstance(e.left, ast.List) else (e.right, e.left)
            if not isinstance(lit, ast.List) or any(isinstance(x, ast.Starred) for x in lit.elts):
                return None
            k = len(lit.elts)
            c = self.peek(cnt, S)
            if k == 1:
                lo, hi = max(c[0], 0), max(c[1], 0)
                ub = dict(c[2]) if c[0] >= 0 else {}  # len == max(0, n): == n only when n >= 0
                lb = dict(c[3])                       # max(0, n) >= n always
                return (lo, min(hi, LENMAX), ub, lb)
            return (0, LENMAX, {}, {})
        if isinstance(e, ast.ListComp) and len(e.generators) == 1 and not e.generators[0].ifs \
                and not e.generators[0].is_async:
            it = e.generators[0].iter
            if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range' \
                    and 'range' not in self.info.shadowed and len(it.args) == 1 and not it.keywords:
                c = self.peek(it.args[0], S)
                if c[0] >= 0:
                    return (c[0], min(c[1], LENMAX), dict(c[2]), dict(c[3]))
                return (0, min(max(c[1], 0), LENMAX), {}, {})
        return (0, LENMAX, {}, {})

    def fresh_elems(self, e, S):
        """The range of every element of a fresh list expression (TOP when unknown)."""
        if isinstance(e, ast.Name):
            if e.id in self.elem and self.elem[e.id] is None:
                return (0, -1, {}, {})      # nothing known stored there yet (Kleene iteration)
            return self.elem_val(e.id)
        lit = None
        if isinstance(e, ast.List):
            lit = e
        elif isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mult):
            lit = e.left if isinstance(e.left, ast.List) else e.right if isinstance(e.right, ast.List) else None
        if lit is None or any(isinstance(x, ast.Starred) for x in lit.elts) or not lit.elts:
            return TOP if lit is None or lit.elts else (0, -1, {}, {})
        vals = [self.peek(x, S) for x in lit.elts]
        return (min(v[0] for v in vals), max(v[1] for v in vals), {}, {})

    def len_of_bytes(self, e, S):
        if isinstance(e, ast.Constant) and isinstance(e.value, bytes):
            return (len(e.value), len(e.value), {}, {})
        return (0, LENMAX, {}, {})

    def range_bounds(self, it, S):
        """(lo value, hi value) of `range(...)` with step 1, else None."""
        if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range'
                and 'range' not in self.info.shadowed and not it.keywords and 1 <= len(it.args) <= 3):
            return None
        args = it.args
        vals = [self.ev(a, S) for a in args]
        if any(isinstance(a, ast.Starred) for a in args):
            return None
        if len(args) == 3:
            st = vals[2]
            if not (st[0] == st[1] == 1):
                return None
        if len(args) == 1:
            return (0, 0, {}, {}), vals[0]
        return vals[0], vals[1]

    def loop_fix(self, entry, body_in_of, body, after=None):
        """Fixed point of a loop head. body_in_of(H) -> state at the top of the body. Returns
        (head state, breaks, normal exits) after a final recording pass."""
        saved = self.recording
        self.recording = False

        def step(H, base):
            self.loops.append([[], []])
            out = self.exec_block(body, body_in_of(H))
            brk, cont = self.loops.pop()
            new = base
            for s in [out] + cont:
                if s is not None:
                    if after is not None:
                        s = dict(s)
                        after(s)
                    new = self.join(new, s)
            return new

        H = entry
        i = 0
        try:
            while True:
                new = step(H, H)
                # converged when every fact of H still holds after one more pass (the join may add
                # facts it can imply, so `new` need not be equal to H for that)
                kept = self.widen(H, new)
                if kept == H:
                    break
                H = kept if i >= 2 else new
                i += 1
                if i > 50:
                    raise _Abort("loop did not settle")
            if i > 2 and saved:
                # One narrowing step: widening threw away bounds the body re-establishes (`w = w * 10
                # + c; if w > 4096 { return }`). The candidate is kept only if it is itself an
                # invariant: entry and one more pass over the body both stay inside it. Only on the
                # recording traversal: inside an enclosing loop's settling passes any invariant
                # will do, and nested narrowing would multiply the work.
                cand = step(H, entry)
                again = step(cand, entry)
                if self.join(again, cand) == cand:
                    H = cand
        finally:
            self.recording = saved
        self.loops.append([[], []])
        self.exec_block(body, body_in_of(H))
        brk, cont = self.loops.pop()
        return H, brk

    def exec_while(self, st, S):
        self.pre_kill(S, [st.test])
        # the test may also bind names on each evaluation
        def body_in(H):
            if H is None:
                return None
            H = dict(H)
            self.pre_kill(H, [st.test])
            self.ev(st.test, H)
            return self.refine(H, st.test, True)
        H, brk = self.loop_fix(S, body_in, st.body)
        H = dict(H) if H is not None else None
        out = None
        if H is not None:
            self.pre_kill(H, [st.test])
            self.ev(st.test, H)
            out = self.refine(H, st.test, False)
        out = self.exec_block(st.orelse, out) if st.orelse else out
        for b in brk:
            out = self.join(out, b) if out is not None else (dict(b) if b is not None else None)
        return out

    def exec_for(self, st, S):
        self.pre_kill(S, [st.iter])
        tgt = st.target
        rb = self.range_bounds(st.iter, S) if isinstance(tgt, ast.Name) and self.is_int(tgt.id) else None
        if rb is None:
            self.ev(st.iter, S)
            bytes_iter = isinstance(st.iter, ast.Name) and self.kind(st.iter.id) in ('bytes', 'bytearray')
            tnames = _names_stored(tgt)
            self.kill(S, tnames)

            def body_in(H):
                if H is None:
                    return None
                H = dict(H)
                self.kill(H, tnames)
                if bytes_iter and isinstance(tgt, ast.Name) and self.is_int(tgt.id):
                    self.set_sym(H, tgt.id, (0, 255, {}, {}))
                elif isinstance(st.iter, ast.Name) and st.iter.id in self.elem and isinstance(tgt, ast.Name) \
                        and self.is_int(tgt.id):
                    self.set_sym(H, tgt.id, self.elem_val(st.iter.id))
                return H
        else:
            # `for i in range(a, b)` runs as `k = a; while k < b { i = k; body; k += 1 }` with a hidden
            # counter k ('#k@N') and the bounds fixed at entry ('#lo@N', '#hi@N'). Relations that
            # hold between k and other symbols survive the `k += 1` (it is an exact shift), which is
            # how `for i in range(n) { xs.append(..) }` ends with len(xs) == n.
            lo_v, hi_v = rb
            key = self.loop_ids.setdefault(id(st), len(self.loop_ids))
            slo, shi, sk = '#lo@%d' % key, '#hi@%d' % key, '#k@%d' % key
            for s in (slo, shi, sk):
                self.drop_refs(S, s)
            self.set_sym(S, slo, lo_v)
            self.set_sym(S, shi, hi_v)
            self.set_sym(S, sk, (lo_v[0], lo_v[1], {slo: 0}, {slo: 0}))
            self.relate_constants(S, sk)
            name = tgt.id

            def body_in(H):
                if H is None:
                    return None
                H = dict(H)
                kv = self.sym_val(H, sk)
                if not self.le(H, None, kv, None, self.sym_val(H, shi), -1):
                    return None                         # k < hi is impossible: the body never runs
                self.drop_refs(H, name)
                self.set_sym(H, name, self.sym_val(H, sk))
                return H

            def after(T):
                self.shift_sym(T, sk, 1)
        H, brk = self.loop_fix(S, body_in, st.body, after if rb is not None else None)
        out = H
        if rb is not None and out is not None:
            out = dict(out)                             # the loop ran out: k >= hi
            if not self.le(out, None, self.sym_val(out, shi), None, self.sym_val(out, sk), 0):
                out = None
        if st.orelse and out is not None:
            out = self.exec_block(st.orelse, dict(out))
        for b in brk:
            out = self.join(out, b) if out is not None else (dict(b) if b is not None else None)
        if rb is not None and out is not None:
            out = dict(out)
            for s in (slo, shi, sk):
                self.drop_refs(out, s)
        return out

    def relate_constants(self, S, sym):
        """`sym` has an exact numeric value: relate it to every other symbol with one, so that
        steps both take later (k += 1 beside len(xs) += 1, count += 1) keep the difference."""
        lo, hi, _, _ = S.get(sym, TOP)
        if lo != hi:
            return
        for s, (slo, shi, _, _) in list(S.items()):
            if s != sym and slo == shi and not s.startswith(('#lo@', '#hi@')):
                d = slo - lo                            # s == sym + d
                self.add_ub(S, s, sym, d); self.add_lb(S, s, sym, d)
                self.add_ub(S, sym, s, -d); self.add_lb(S, sym, s, -d)

    def exec_try(self, st, S):
        """A handler can start anywhere in the try body: from the state before `try` with every
        name the body may assign (and every list it mentions) forgotten. A `finally` may run after
        any point of the whole statement, so it starts from that state over the whole statement
        joined with the normal exits; a break/continue that would run a `finally` on its way out
        is not modelled, so such a function is not analysed at all."""
        def forgotten(stmts):
            T = dict(S)
            for x in stmts:
                self.forget(T, x, unanalysed=False)     # the statements themselves are analysed
            return T
        if st.finalbody and any(any(_loop_exits(x)) for x in st.body + st.orelse
                                + [y for h in st.handlers for y in h.body]):
            raise _Abort("break or continue through finally")
        handler_in = forgotten(st.body)
        out = self.exec_block(st.body, S)
        if st.orelse and out is not None:
            out = self.exec_block(st.orelse, out)
        for h in st.handlers:
            hs = dict(handler_in)
            if h.name:
                self.kill(hs, [h.name])
            r = self.exec_block(h.body, hs)
            if r is not None:
                out = self.join(out, r) if out is not None else dict(r)
        if st.finalbody:
            anywhere = forgotten(st.body + st.orelse + [h for h in st.handlers])
            fin_in = self.join(out, anywhere) if out is not None else anywhere
            r = self.exec_block(st.finalbody, fin_in)
            return r if out is not None else None
        return out
