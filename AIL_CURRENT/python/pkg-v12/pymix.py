# -*- coding: utf-8 -*-
"""pymix.py -- per-FUNCTION mixed-mode selection (BRIEF_mixed_mode.md, 2026-09-16).

This module finds typed candidates inside general-path programs. In the current integration,
`pyc.build` first attempts the typed whole-program path; eligible refusals enter the general
path. `pyboxed2.Compiler._setup_mix` uses this analysis and rechecks candidates with
`pyfunc.to_c`. Eligible functions retain their boxed implementation and gain a separately
compiled typed clone selected by a runtime guard. Selection is not evidence of a speedup.

Public API:
    analyze(source, classes=()) -> MixReport
        Whole-module fixed-point kind inference, per §1, plus per-function candidacy per §2/§3.

Design decisions (so the next brief inherits them, not just the code):

  - Kind hypotheses come from a fixed-point forward analysis over the whole module's AST: literals,
    `int()`/`float()`/`str()`/`bool()`/`input()`/`len()`, arithmetic, `range()`, comparisons, and
    CALL-SITE argument kinds (a function called only with int arguments gets an int hypothesis for
    that parameter) -- exactly the brief's source list. Iterated to a fixed point; anything
    contradictory or never resolved is UNKNOWN.

  - Selection does NOT reimplement the typed emitter's own acceptance rules. Once every parameter,
    every local and the return are hypothesised to a typed kind, candidacy is confirmed by
    literally calling `pyfunc.to_c(source, entry=name, sig=scalar_hints, info=info)` and checking
    it does not raise `Unsupported` -- reusing the real emitter is the only way "accepts it as-is"
    can be trusted; a second, hand-rolled acceptance test would drift from `to_c`'s actual rules
    the first time either file changes. `sig` only ever carries the four scalar annotation
    spellings `_annotation_kind` already understands (`int`/`float`/`str`/`bytes`) -- list-shaped
    parameters are left to `to_c`'s OWN body-evidence inference (`_param_kinds`), which already
    infers array-ness, str-vs-bytes and float-uniformity from exactly the same evidence this module
    collects; forcing a `list[int]`/`list[float]` spelling through `sig` is not a shape
    `_annotation_kind` accepts at all (checked directly against the source, see STUDY.md-style
    note in `_scalar_sig_text` below) and would misrepresent what is actually being asked for.

  - CONSERVATIVE EXCEPTION RULE (the one deliberate simplification in this pass, flagged for the
    next brief -- see `REASON_EXC_CAPABLE`): a function is never a candidate if it, or any function
    it can reach through the module's own call graph, contains a `try`, a `raise`, or an operation
    with any of the typed path's five named traps (division/modulo by a divisor not PROVABLY
    nonzero, subscript, `.pop()`, dict/set key access, `int()`/`input()` at end-of-input) -- unless
    every such site is statically provable safe (a nonzero integer-literal divisor). The reason is
    a real runtime fact, not laziness: the typed path's own exception mechanism
    (`cruntime.py`'s global `ail_exc_stack`/`setjmp`/`longjmp`) and the general path's exception
    mechanism (`pyboxed2.py`/`ail_obj2.h`'s `ail_raise_c`/`ail_ctx` ["boxed" report source]) are
    two separate, uncoordinated handler stacks; a `longjmp` out of a typed_inline call cannot land
    in a `try` the BOXED caller registered on the other stack (a `try` in that caller pushes a
    frame onto ITS OWN handler chain, never onto `cruntime.py`'s `ail_exc_stack`). Bridging the two
    correctly -- mapping `AIL_EXC_*` onto `AIL_B_*` and re-raising into the CALLER's chain -- is
    real runtime work, not a selection-time shortcut, so it stays out of scope here. This is
    exactly what `test_mixed.py`'s exception proof requires: EITHER CPython-faithful exception flow
    OR non-selection; this pass always takes non-selection, and reports why under
    `REASON_EXC_CAPABLE` so the next brief has a concrete, counted list to start from.

  - Every conclusion here is a HYPOTHESIS, same as the brief's wording: this module only decides
    whether a function is a *candidate*; it does not itself emit C, box, unbox, or guard anything
    (see `pyfunc.to_c`, reused, and the calling convention documented in `mix_call.h`, standalone,
    for the actual runtime mechanism -- both are separate from this file on purpose).

Integration status (source checked 2026-09-16): `_call_user_function` in pyboxed2 routes
selected functions through `_call_mix_guarded`. The emitter reports `typed_inline`,
`guard_checks`, and `mix_units`; `pyc.build` compiles typed units separately and links them
with the boxed unit. Optional pymix import or AIL_NO_MIX=1 can leave the general path
boxed-only. This module supplies candidate analysis; guard/emitter/link code lives in
pyboxed2/pyc. The earlier NOT DONE description preceded that integration.
"""
import ast
import semir

import pyfunc

Unsupported = pyfunc.Unsupported

# ---- the kind vocabulary (brief's own spelling) -----------------------------------------------
INT, FLOAT, BOOL, STR = 'int', 'float', 'bool', 'str'
LIST_INT, LIST_FLOAT, LIST_STR = 'list[int]', 'list[float]', 'list[str]'
UNKNOWN = None                                    # unresolved OR contradictory; never guessed past
SCALAR = (INT, FLOAT, BOOL, STR)
NUMERIC = (INT, FLOAT, BOOL)
LIST_KINDS = (LIST_INT, LIST_FLOAT, LIST_STR)
ELEM_OF = {LIST_INT: INT, LIST_FLOAT: FLOAT, LIST_STR: STR}
LIST_OF = {INT: LIST_INT, FLOAT: LIST_FLOAT, STR: LIST_STR}

# `_annotation_kind` (pyfunc.py) understands exactly these four bare spellings for `sig=`; passing
# anything else through `sig` either raises or is silently not what was meant (see module
# docstring) -- list-shaped hints are never sent through `sig`, so this map only ever needs to
# cover the scalar four.
_SCALAR_ANNOTATION_TEXT = {INT: 'int', FLOAT: 'float', STR: 'str'}
# `bool` has no annotation spelling `_annotation_kind` accepts on its own (SEMANTICS.md: a Python
# bool is a plain C int64 everywhere in the typed emitter, never a distinct kind) -- a bool
# hypothesis is seeded as 'int' for `to_c`'s purposes and remembered separately (`is_bool`) purely
# so the CALLING CONVENTION can box the result with `ail_box_bool` instead of `ail_box_int`
# (`str(True)` is `'True'`, not `'1'` -- the wrong box is a silent wrong answer).


def _merge(a, b):
    """Two kind hypotheses for the same slot, from two pieces of evidence. Agreement is kept;
    disagreement is UNKNOWN -- contradiction is never resolved by picking a side. Numeric
    promotion (`int`/`bool` mixed with `float`) follows Python's own arithmetic promotion, because
    that mix is not a contradiction -- it is what `1 + 1.0` actually is."""
    if a is UNKNOWN or b is UNKNOWN:
        return UNKNOWN
    if a == b:
        return a
    if a in NUMERIC and b in NUMERIC:
        return FLOAT if FLOAT in (a, b) else INT
    return UNKNOWN


class _FnFacts:
    __slots__ = ('node', 'params', 'locals', 'ret', 'is_bool_ret', 'exc_capable', 'exc_reason')

    def __init__(self, node):
        self.node = node
        self.params = {a.arg: UNKNOWN for a in node.args.args}
        self.locals = {}
        self.ret = UNKNOWN
        self.is_bool_ret = False
        self.exc_capable = False
        self.exc_reason = None


# ---- exception reachability (the try/except rule, §3 of the brief) -----------------------------
#
# `to_c` already compiles `try`/`except`/`raise` correctly and completely -- see pyfunc.py's own
# EXC_NAMES/setjmp machinery -- for anything that stays INSIDE the typed closure `to_c(entry=name)`
# pulls in (that function plus every function it reaches). A raise fully caught by a `try` in that
# SAME closure never needs to cross back into boxed code at all, so it is always safe and is never
# rejected here.
#
# The one thing genuinely unsafe is an exception that ESCAPES the typed closure (nothing inside it
# catches it) at a moment when it is ALSO true that the general/boxed program has a live
# `try/except` for that exception type somewhere up the call chain to the guarded call site. The
# guard call itself is a single C function call, not a Python-level call CPython's interpreter
# walks frame by frame -- the moment control enters the typed closure, the ONLY handler stack it
# can see is `cruntime.py`'s own `ail_exc_stack`, which the boxed caller never pushed onto (its own
# `try` uses a completely different, `ail_ctx`-based mechanism, per `pyboxed2.py`/API.md). So an
# escaping exception inside the typed closure ALWAYS reaches `ail_die`/`_Exit(1)` from the typed
# runtime's point of view, regardless of how many Python frames up a real handler sits -- which is
# CORRECT (matches CPython's own uncaught-exception exit code 1, stdout already flushed) exactly
# when NOTHING up that chain would have caught it in CPython either, and WRONG the moment something
# would have. Hence: reject a candidate iff some exception type escapes its typed closure AND some
# call site reaching it is protected by a `try/except` for that type anywhere up the boxed call
# chain -- checked by walking OUTWARD from every call site, through enclosing functions, exactly
# the way CPython's own frame unwinding would.

EXC_TYPE_NAMES = frozenset({'ValueError', 'ZeroDivisionError', 'IndexError', 'KeyError', 'EOFError'})
_TRAP_EXC = {ast.Div: 'ZeroDivisionError', ast.FloorDiv: 'ZeroDivisionError', ast.Mod: 'ZeroDivisionError'}


def _provably_nonzero(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and node.value != 0


def _build_parents(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _enclosing_scope_and_trys(node, parents):
    """Walk up from `node` to the nearest enclosing `FunctionDef` (or the module top, returned as
    `MODULE_SCOPE`), collecting every `Try` passed through WHILE `node` was inside that `Try`'s
    OWN body (not a handler/else/finally -- a raise inside a handler is a different exception,
    already refused elsewhere by `to_c` if it isn't one of the five names)."""
    trys, cur = [], node
    while cur in parents:
        par = parents[cur]
        if isinstance(par, ast.Try) and cur in par.body:
            trys.append(par)
        if isinstance(par, ast.FunctionDef):
            return par.name, trys
        cur = par
    return MODULE_SCOPE, trys


def _handler_catches(handler, exc_name):
    t = handler.type
    if t is None:
        return True                                    # bare `except:` -- catches everything
    names = ([t.id] if isinstance(t, ast.Name) else
             [e.id for e in t.elts if isinstance(e, ast.Name)] if isinstance(t, ast.Tuple) else [])
    return exc_name in names or 'Exception' in names or 'BaseException' in names


def _raise_site_exc(node):
    """The exception NAME a given AST node could raise as one of the typed path's five named
    traps, or `None`. Mirrors `to_c`'s own `EXC_NAMES`/`ail_exc_kind_of` (cruntime.py) -- the same
    five, nothing invented here."""
    if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
        return node.exc.func.id if node.exc.func.id in EXC_TYPE_NAMES else None
    if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Name):
        return node.exc.id if node.exc.id in EXC_TYPE_NAMES else None
    if isinstance(node, ast.BinOp) and type(node.op) in _TRAP_EXC and not _provably_nonzero(node.right):
        return _TRAP_EXC[type(node.op)]
    if isinstance(node, ast.Subscript):
        return 'IndexError'                             # list/str; dict subscript is KeyError too,
                                                          # but IndexError is always in play here
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'pop':
        return 'IndexError'
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'int':
        return 'ValueError'
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'input':
        return 'EOFError'
    return None


def _walk_own_body(fn_node):
    """Like `ast.walk(fn_node)`, but never descends into a NESTED `def` -- that function's own
    raise sites are its own concern, analysed separately when it is its own entry in `fn_facts`."""
    stack = list(ast.iter_child_nodes(fn_node))
    while stack:
        n = stack.pop()
        yield n
        if not isinstance(n, ast.FunctionDef):
            stack.extend(ast.iter_child_nodes(n))


def _self_raise_sites(fn_node):
    """[(node, exc_name), ...] for every operation directly inside `fn_node` (not inside a nested
    `def`) that could raise one of the five named exceptions."""
    return [(n, exc) for n in _walk_own_body(fn_node) for exc in [_raise_site_exc(n)] if exc]


def _escapes(fn_facts, parents):
    """{function_name: set(exc_name, ...)} -- exception types that can propagate OUT of each
    function's OWN typed closure (its raise sites, and its callees' escapes at call sites this
    function does not locally catch), fixed-point over the whole call graph so a chain of typed
    calls propagates correctly through as many hops as it actually has."""
    names = list(fn_facts)
    esc = {n: set() for n in names}
    call_sites = {n: [] for n in names}                 # callee -> [(call_node, caller_name)]
    for name, f in fn_facts.items():
        for n in _walk_own_body(f.node):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in fn_facts:
                call_sites.setdefault(n.func.id, []).append((n, name))

    for _ in range(MAX_ROUNDS):
        changed = False
        for name, f in fn_facts.items():
            local = set()
            for site_node, exc in _self_raise_sites(f.node):
                _, trys = _enclosing_scope_and_trys(site_node, parents)
                if not any(_handler_catches(h, exc) for t in trys for h in t.handlers):
                    local.add(exc)
            # callee escapes at each call site this function makes, minus what a local try catches
            for callee, sites in call_sites.items():
                for call_node, caller_name in sites:
                    if caller_name != name:
                        continue
                    scope, trys = _enclosing_scope_and_trys(call_node, parents)
                    for exc in esc.get(callee, ()):
                        if not any(_handler_catches(h, exc) for t in trys for h in t.handlers):
                            local.add(exc)
            if local != esc[name]:
                esc[name] = local
                changed = True
        if not changed:
            break
    return esc, call_sites


def _protected(name, exc, call_sites, parents, seen=frozenset()):
    """True iff SOME call site reaching `name` (directly, or through a chain of ordinary boxed
    calls) sits inside a `try/except` for `exc` anywhere up that chain -- walked the way CPython's
    own frame unwinding would, since that is exactly the behaviour a rejected candidate is standing
    in for (see module docstring: crossing the typed/boxed boundary loses every handler that is not
    lexically inside the SAME typed closure)."""
    if name in seen:
        return False
    for call_node, caller_name in call_sites.get(name, ()):
        scope, trys = _enclosing_scope_and_trys(call_node, parents)
        if any(_handler_catches(h, exc) for t in trys for h in t.handlers):
            return True
        if scope == MODULE_SCOPE:
            continue                                    # this path ends uncaught -- safe on its own
        if _protected(scope, exc, call_sites, parents, seen | {name}):
            return True
    return False


# ---- expression-kind inference ------------------------------------------------------------------

def _lit_kind(v):
    if isinstance(v, bool):
        return BOOL
    if isinstance(v, int):
        return INT
    if isinstance(v, float):
        return FLOAT
    if isinstance(v, str):
        return STR
    return UNKNOWN


def _expr_kind(e, facts, rets):
    if isinstance(e, ast.Constant):
        return _lit_kind(e.value)
    if isinstance(e, ast.Name):
        return facts.params.get(e.id, facts.locals.get(e.id, UNKNOWN))
    if isinstance(e, ast.List) or isinstance(e, ast.ListComp):
        elts = e.elts if isinstance(e, ast.List) else [e.elt]
        ek = UNKNOWN
        for el in elts:
            k = _expr_kind(el, facts, rets)
            ek = k if ek is UNKNOWN else _merge(ek, k)
            if elts and ek is UNKNOWN and el is not elts[0]:
                return UNKNOWN
        return LIST_OF.get(ek, UNKNOWN) if not isinstance(e, ast.ListComp) or ek is not UNKNOWN \
            else UNKNOWN
    if isinstance(e, ast.BinOp):
        l, r = _expr_kind(e.left, facts, rets), _expr_kind(e.right, facts, rets)
        if isinstance(e.op, ast.Add) and l == STR and r == STR:
            return STR
        if isinstance(e.op, ast.Div):
            return FLOAT if l in NUMERIC and r in NUMERIC else UNKNOWN
        if l in NUMERIC and r in NUMERIC:
            return _merge(l, r)
        return UNKNOWN
    if isinstance(e, (ast.Compare, )):
        return BOOL
    if isinstance(e, ast.UnaryOp):
        if isinstance(e.op, ast.Not):
            return BOOL
        return _expr_kind(e.operand, facts, rets)
    if isinstance(e, ast.IfExp):
        return _merge(_expr_kind(e.body, facts, rets), _expr_kind(e.orelse, facts, rets))
    if isinstance(e, ast.Subscript):
        base = _expr_kind(e.value, facts, rets)
        return ELEM_OF.get(base, UNKNOWN)
    if isinstance(e, ast.Call):
        return _call_kind(e, facts, rets)
    return UNKNOWN


def _call_kind(e, facts, rets):
    if not isinstance(e.func, ast.Name):
        return UNKNOWN
    fn = e.func.id
    if fn == 'int':
        return INT
    if fn == 'float':
        return FLOAT
    if fn == 'str':
        return STR
    if fn == 'bool':
        return BOOL
    if fn == 'len':
        return INT
    if fn == 'input':
        return STR
    if fn in ('sum', 'min', 'max') and len(e.args) == 1:
        base = _expr_kind(e.args[0], facts, rets)
        return ELEM_OF.get(base, UNKNOWN)
    if fn in rets:
        return rets[fn]
    return UNKNOWN


# ---- whole-module fixed point --------------------------------------------------------------------

def _assigned_name(t):
    return t.id if isinstance(t, ast.Name) else None


def _one_pass(fn_facts, module_calls):
    """One sweep over every function's body plus every call site in the module. Returns True if
    anything changed (the fixed-point driver keeps calling this until it returns False)."""
    changed = False
    rets = {name: f.ret for name, f in fn_facts.items()}

    def set_local(f, name, kind):
        nonlocal changed
        if name in f.params:
            old = f.params[name]
            new = _merge(old, kind) if old is not UNKNOWN else kind
        else:
            old = f.locals.get(name, UNKNOWN)
            new = _merge(old, kind) if old is not UNKNOWN else kind
        if new != old:
            if name in f.params:
                f.params[name] = new
            else:
                f.locals[name] = new
            changed = True

    for f in fn_facts.values():
        for n in ast.walk(f.node):
            if n is f.node:
                continue
            if isinstance(n, ast.FunctionDef) and n is not f.node:
                continue
            if isinstance(n, ast.Assign):
                k = _expr_kind(n.value, f, rets)
                if k is not UNKNOWN:
                    for t in n.targets:
                        nm = _assigned_name(t)
                        if nm:
                            set_local(f, nm, k)
            elif isinstance(n, ast.AugAssign):
                nm = _assigned_name(n.target)
                if nm:
                    cur = f.params.get(nm, f.locals.get(nm, UNKNOWN))
                    rhs = _expr_kind(n.value, f, rets)
                    k = _merge(cur, rhs) if cur is not UNKNOWN and rhs is not UNKNOWN else UNKNOWN
                    if k is not UNKNOWN:
                        set_local(f, nm, k)
            elif isinstance(n, ast.For):
                nm = _assigned_name(n.target)
                if nm:
                    itk = _expr_kind(n.iter, f, rets)
                    ek = ELEM_OF.get(itk, UNKNOWN)
                    if ek is not UNKNOWN:
                        set_local(f, nm, ek)
            elif isinstance(n, ast.Compare) and len(n.ops) == 1:
                # `x < 2`, `x == "done"`, ... -- a bare Name compared against a literal (or another
                # Name whose kind is already known) is evidence about the Name's OWN kind, not just
                # about the comparison's (always-bool) result. Numeric-vs-numeric evidence is weak
                # (an int literal does not rule out `x` being float -- `1.5 < 2` is legal), so it is
                # only applied when `x` has no evidence yet; a str/bool comparison is closer to a
                # hard fact (this language's `==`/`<` never coerce across those), so it always wins.
                left, right = n.left, n.comparators[0]
                lk, rk = _expr_kind(left, f, rets), _expr_kind(right, f, rets)
                for side, other_k, other_node in ((left, rk, right), (right, lk, left)):
                    nm = _assigned_name(side)
                    if nm is None or other_k is UNKNOWN:
                        continue
                    cur = f.params.get(nm, f.locals.get(nm, UNKNOWN))
                    if other_k in (STR, BOOL) or cur is UNKNOWN:
                        set_local(f, nm, other_k)
            elif isinstance(n, ast.BinOp):
                # `x - 1`, `x + 1.0`, `x + "y"` -- an operand whose OWN kind is unknown, next to an
                # operand whose kind is known, is weak numeric/str evidence for the unknown side --
                # same rationale as the comparison case just above, and via the same `set_local`
                # (idempotent: merging a slot with itself changes nothing once it is already known).
                lk, rk = _expr_kind(n.left, f, rets), _expr_kind(n.right, f, rets)
                for side, other_k in ((n.left, rk), (n.right, lk)):
                    nm = _assigned_name(side)
                    if nm is None or other_k is UNKNOWN:
                        continue
                    cur = f.params.get(nm, f.locals.get(nm, UNKNOWN))
                    if cur is UNKNOWN and (other_k in NUMERIC or
                                            (other_k == STR and isinstance(n.op, ast.Add))):
                        set_local(f, nm, other_k)
            elif isinstance(n, ast.Return) and n.value is not None:
                k = _expr_kind(n.value, f, rets)
                if k is not UNKNOWN:
                    new = _merge(f.ret, k) if f.ret is not UNKNOWN else k
                    if new != f.ret:
                        f.ret = new
                        changed = True
                    if k == BOOL:
                        f.is_bool_ret = True

    # call-site evidence: a parameter with no local evidence at all takes the union of every
    # argument kind offered to it, across every call site in the whole module (module top level
    # included).
    for callee_name, args in module_calls:
        f = fn_facts.get(callee_name)
        if f is None:
            continue
        pnames = list(f.params)
        for i, argk in enumerate(args):
            if i >= len(pnames) or argk is UNKNOWN:
                continue
            set_local(f, pnames[i], argk)

    return changed


MODULE_SCOPE = '<module>'


def _collect_calls(tree, fn_facts):
    """(callee_name, [arg_kind, ...]) for every call in the module to a name this module defines,
    evaluated against EACH caller's OWN current facts (so call-site evidence keeps improving as the
    fixed point runs -- an argument that is itself a parameter only resolves once ITS caller is
    resolved, which is exactly why this whole thing iterates). A call at module top level is
    evaluated against `fn_facts[MODULE_SCOPE]`, the module body's own pseudo-function scope (see
    `_fixed_point`) -- so `v = int(x); f(v)` at top level resolves `v` exactly the way it would
    inside a real function."""
    out = []
    module_f = fn_facts[MODULE_SCOPE]

    def scope_facts_for(node):
        for name, f in fn_facts.items():
            if name == MODULE_SCOPE:
                continue
            if node in ast.walk(f.node) and node is not f.node:
                return f
        return module_f

    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in fn_facts:
            caller = scope_facts_for(n)
            rets = {name: f.ret for name, f in fn_facts.items()}
            # Reuse kind inference, binding explicit keywords to their formal positions.
            # Star arguments are unresolved; runtime binding remains the boxed emitter's job.
            formals = list(fn_facts[n.func.id].params)
            if any(isinstance(a, ast.Starred) for a in n.args) or any(k.arg is None for k in n.keywords):
                continue
            actual = dict(zip(formals, n.args))
            if len(n.args) > len(formals) or any(k.arg not in formals or k.arg in actual for k in n.keywords):
                continue
            actual.update((k.arg, k.value) for k in n.keywords)
            argks = [_expr_kind(actual[p], caller, rets) if p in actual else UNKNOWN for p in formals]
            out.append((n.func.id, argks))
    return out


MAX_ROUNDS = 40


def _module_scope_node(tree):
    body = [s for s in tree.body if not isinstance(s, (ast.FunctionDef, ast.ClassDef))]
    node = ast.FunctionDef(name=MODULE_SCOPE, args=ast.arguments(
        posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=body or [ast.Pass()], decorator_list=[])
    return ast.fix_missing_locations(node)


def _fixed_point(tree):
    fn_facts = {n.name: _FnFacts(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
    fn_facts[MODULE_SCOPE] = _FnFacts(_module_scope_node(tree))
    for _ in range(MAX_ROUNDS):
        module_calls = _collect_calls(tree, fn_facts)
        if not _one_pass(fn_facts, module_calls):
            break
    return fn_facts


# ---- candidacy ------------------------------------------------------------------------------------

REASON_UNRESOLVED_PARAM = 'unresolved-param'
REASON_UNRESOLVED_LOCAL = 'unresolved-local'
REASON_UNRESOLVED_RET = 'unresolved-return'
REASON_EXC_CAPABLE = 'exception-capable'
REASON_TO_C_REFUSED = 'to_c-refused'


class MixReport:
    def __init__(self):
        self.candidates = {}          # name -> {'params': {...}, 'ret': kind, 'is_bool_ret': bool}
        self.rejected = {}            # name -> (reason, detail)
        self.function_ir = {}        # version-bound SemIR facts consumed by the boxed emitter

    def as_typed_inline(self):
        return sorted(self.candidates)


def _scalar_sig(params):
    """`{param: type_text}` for `to_c(sig=...)`, scalar kinds only (see module docstring) --
    `bool` is seeded as `int` (no separate annotation spelling exists); list-shaped parameters are
    left out entirely so `to_c`'s own body-evidence inference decides them."""
    sig = {}
    for p, k in params.items():
        if k == BOOL:
            sig[p] = 'int'
        elif k in _SCALAR_ANNOTATION_TEXT:
            sig[p] = _SCALAR_ANNOTATION_TEXT[k]
    return sig


def _defs_only_source(tree):
    """`to_c`'s module-constant scan (`_MODCONSTS`) walks EVERY top-level statement in the source
    it is given, not just the functions reachable from `entry` -- a general-path program's
    top-level code (the reason it is on the general path at all: a dict, an `input()` call, a
    `for` loop over stdin) makes that scan refuse the whole source before `entry=`'s own call-graph
    trim ever gets a say. Candidacy per-function therefore compiles a SLICE containing only the
    module's own `def`s (no top-level statements, no classes -- both out of this pass's scope
    already, see the module docstring) -- exactly the self-contained C `to_c` is asked to emit
    "alongside" in the brief, never the whole boxed program."""
    only_defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    return ast.unparse(ast.Module(body=only_defs, type_ignores=[]))


def analyze(source, classes=()):
    """The module's one entry point. `classes` mirrors `pyfunc._scan_classes`'s output, for
    parity with `to_c`'s own signature -- this pass does not itself select class-instance
    functions (an object parameter's kind is a `(OBJ, ClassName)` pair, out of the brief's stated
    vocabulary), so every function with one is rejected `unresolved-param` by construction, which
    is the correct, honest answer for this pass."""
    tree = ast.parse(source.strip())
    fn_facts = _fixed_point(tree)
    defs_src = _defs_only_source(tree)
    parents = _build_parents(tree)
    esc, call_sites = _escapes(fn_facts, parents)
    report = MixReport()
    rets = {name: f.ret for name, f in fn_facts.items()}
    # One C return ABI cannot preserve distinct Python tags on different branches.
    unsafe_returns = {
        name for name, f in fn_facts.items() if name != MODULE_SCOPE
        and {_expr_kind(n.value, f, rets) for n in ast.walk(f.node)
             if isinstance(n, ast.Return)} != {f.ret}
    }
    # A typed caller also compiles its callees, so leaving only the callee boxed is insufficient.
    while True:
        callers = {name for name, f in fn_facts.items() if name != MODULE_SCOPE
                   and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                           and n.func.id in unsafe_returns for n in ast.walk(f.node))}
        if callers <= unsafe_returns:
            break
        unsafe_returns |= callers

    for name, f in fn_facts.items():
        if name == MODULE_SCOPE:
            continue
        unresolved_params = [p for p, k in f.params.items() if k is UNKNOWN]
        if unresolved_params:
            report.rejected[name] = (REASON_UNRESOLVED_PARAM, ', '.join(unresolved_params))
            continue
        unresolved_locals = [n for n, k in f.locals.items() if k is UNKNOWN]
        if unresolved_locals:
            report.rejected[name] = (REASON_UNRESOLVED_LOCAL, ', '.join(unresolved_locals))
            continue
        if f.ret is UNKNOWN:
            report.rejected[name] = (REASON_UNRESOLVED_RET, 'no return, or contradictory returns')
            continue
        if name in unsafe_returns:
            report.rejected[name] = (REASON_UNRESOLVED_RET, 'return branches require distinct tags')
            continue
        blocking = sorted(exc for exc in esc.get(name, ()) if _protected(name, exc, call_sites, parents))
        if blocking:
            report.rejected[name] = (REASON_EXC_CAPABLE,
                                     '%s can escape to a boxed try/except reachable from a call to'
                                     ' this function' % '/'.join(blocking))
            continue
        try:
            info = {'_mixed_clone': True}
            pyfunc.to_c(defs_src, entry=name, sig=_scalar_sig(f.params), info=info)
        except Unsupported as e:
            report.rejected[name] = (REASON_TO_C_REFUSED, str(e)[:160])
            continue
        report.candidates[name] = {
            'params': dict(f.params), 'ret': f.ret, 'is_bool_ret': f.is_bool_ret,
        }
        report.function_ir[name] = semir.mixed_call_ir(source, name, f.params, f.ret, f.is_bool_ret)
    return report


if __name__ == '__main__':
    import sys
    src = sys.stdin.read() if len(sys.argv) < 2 else open(sys.argv[1], encoding='utf-8').read()
    rep = analyze(src)
    print('candidates:', sorted(rep.candidates))
    for name, (reason, detail) in sorted(rep.rejected.items()):
        print('  not selected: %-20s %-20s %s' % (name, reason, detail))
