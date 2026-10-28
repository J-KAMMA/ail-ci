# -*- coding: utf-8 -*-
"""dictviews.py -- where the typed path may not see a dict view as a value (DIFFERENCES C105).

`d.keys()`, `d.values()` and `d.items()` are views in CPython: `print(d.keys())` writes `dict_keys(['a'])`, `d.keys() == {'a'}`
is a set comparison, `d.keys() & s` is a set. The typed path lowers each of them to the list of keys / values / pairs, which
is right where the list is only walked (a loop, `len`, `sorted`, `list`, `in`, `join`, ...) and wrong wherever the view itself
is looked at (printed, compared, combined with `&`, indexed, returned, stored in a field). The general path keeps a marker on
the snapshot (cruntime `ail__view_kind`) and prints, compares and combines it as a view.

`escape(tree)` returns the first node where a view (a `.keys()` / `.values()` / `.items()` call without arguments, or a name
that holds one) is used in a way that is not one of the walking contexts below, or None. The typed path refuses that
program by name (`pyfunc.to_c`); the default build then compiles it on the general path.
"""
import ast

# a call to one of these walks the view (or copies it) and never shows it
_WALKERS = frozenset((
    'len', 'list', 'sorted', 'tuple', 'set', 'frozenset', 'sum', 'min', 'max', 'any', 'all', 'enumerate', 'zip',
    'reversed', 'iter', 'bool', 'dict', 'map', 'filter'))
_WALKING_METHODS = frozenset((
    'join', 'extend', 'update', 'union', 'intersection', 'difference', 'symmetric_difference', 'issubset', 'issuperset',
    'isdisjoint', 'fromkeys', 'difference_update', 'intersection_update', 'symmetric_difference_update'))
_VIEW_METHODS = ('keys', 'values', 'items')


def _is_view_call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _VIEW_METHODS
            and not node.args and not node.keywords)


def _parents(tree):
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    return parent


def _is_view(node, names):
    return _is_view_call(node) or (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names)


def _walks(node, parent):
    """True when `node` (a view) is used only to walk it."""
    p = parent.get(node)
    if isinstance(p, (ast.For, ast.AsyncFor)):
        return p.iter is node
    if isinstance(p, ast.comprehension):
        return p.iter is node
    if isinstance(p, ast.Call):
        if any(k.value is node for k in p.keywords) and not (isinstance(p.func, ast.Name) and p.func.id in ('sorted', 'min', 'max', 'sum')):
            return False
        if node in p.args:
            if isinstance(p.func, ast.Name):
                return p.func.id in _WALKERS
            return isinstance(p.func, ast.Attribute) and p.func.attr in _WALKING_METHODS
        return False
    if isinstance(p, ast.Compare):
        return len(p.ops) == 1 and p.comparators[0] is node and isinstance(p.ops[0], (ast.In, ast.NotIn))
    if isinstance(p, ast.Starred):
        return True
    if isinstance(p, ast.Expr):
        return True
    if isinstance(p, (ast.If, ast.While, ast.IfExp, ast.Assert)):
        return p.test is node
    if isinstance(p, ast.UnaryOp):
        return isinstance(p.op, ast.Not)
    return False


_MUTATORS = frozenset(('pop', 'popitem', 'clear', 'update', 'setdefault', '__setitem__', '__delitem__', 'move_to_end',
                       'subtract'))


def _callee(node):
    f = node.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


def _direct_mutation(node):
    """A construct that can change a dict: an item store or delete, `|=`, a call of `pop` / `update` / `clear` ..."""
    if isinstance(node, (ast.Subscript,)) and isinstance(node.ctx, (ast.Store, ast.Del)):
        return True
    if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.BitOr):
        return True
    return isinstance(node, ast.Call) and _callee(node) in _MUTATORS


def _mutating_functions(tree):
    """Names of the program's functions, methods and classes (through `__init__`) that may change a dict, directly or
    through a call of another such name (a fixed point; same-named definitions are merged)."""
    bodies = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bodies.setdefault(node.name, []).append(node)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Lambda):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    bodies.setdefault(t.id, []).append(node.value)
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, ast.FunctionDef) and m.name == '__init__':
                    bodies.setdefault(node.name, []).append(m)
    bad = set()
    calls = {}
    for name, defs in bodies.items():
        called = set()
        for d in defs:
            for n in ast.walk(d):
                if _direct_mutation(n):
                    bad.add(name)
                elif isinstance(n, ast.Call) and _callee(n):
                    called.add(_callee(n))
        calls[name] = called
    changed = True
    while changed:
        changed = False
        for name, called in calls.items():
            if name not in bad and called & bad:
                bad.add(name)
                changed = True
    return bad, set(bodies)


def _held(node, parent, defined):
    """True when `node` (a view, or a name that holds one) ends up kept: returned, bound, stored, or handed to a function
    that is not a built-in of the program's own, after any number of enclosing displays."""
    q = parent.get(node)
    while isinstance(q, (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.Starred)):
        node, q = q, parent.get(q)
    if isinstance(q, (ast.Return, ast.Yield, ast.YieldFrom, ast.Lambda, ast.Assign, ast.AnnAssign, ast.NamedExpr,
                      ast.AugAssign, ast.Await)):
        return not (isinstance(q, (ast.Assign, ast.AnnAssign)) and q.value is not node)
    if isinstance(q, ast.keyword):
        q = parent.get(q)
    if isinstance(q, ast.Call) and node is not q.func:
        c = q.func
        if isinstance(c, ast.Attribute):
            return c.attr in defined or c.attr not in _WALKING_METHODS
        return not (isinstance(c, ast.Name) and c.id not in defined and c.id in dir(__import__('builtins')))
    return False


def stored(tree):
    """The first `d.keys()` / `.values()` / `.items()` call whose result is kept where a later change of the dict could
    show (DIFFERENCES C106, C107), else None. In CPython a kept view follows the dict; here it is a snapshot, so it would
    show the old contents and a loop over it would not raise "dictionary changed size during iteration". Kept means: bound
    to a field or an item, put in a display, or bound to a name that is then handed on (returned, stored, passed to a
    function of the program) or that may be read after a statement that can change a dict (an item store or delete, a
    call of `pop` / `update` / `clear` ..., a call of a function of the program that has one), a mutation
    counts when a read of the name follows it, or both are in one loop."""
    parent = _parents(tree)
    bad = None
    defined = None
    for node in ast.walk(tree):
        if not _is_view_call(node) or isinstance(node.func.value, (ast.Dict, ast.DictComp)):
            continue                    # (the view of a dict display has no other name, so nothing can change it)
        p = parent.get(node)
        if bad is None:
            bad, defined = _mutating_functions(tree)
        if isinstance(p, (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.Starred)):
            if _held(node, parent, defined):
                return node
            continue
        if isinstance(p, ast.NamedExpr) and p.value is node:
            return node
        if isinstance(p, ast.Assign) and p.value is node:
            targets = p.targets
        elif isinstance(p, ast.AnnAssign) and p.value is node:
            targets = [p.target]
        else:
            continue
        if not all(isinstance(t, ast.Name) for t in targets):
            return node
        names = set(t.id for t in targets)
        scope = p
        while scope in parent and not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.Module)):
            scope = parent[scope]
        start = p.lineno
        walker = p
        while walker in parent and walker is not scope:
            if isinstance(walker, (ast.For, ast.AsyncFor, ast.While)):
                start = min(start, walker.lineno)
            walker = parent[walker]
        loads = [n for n in ast.walk(scope) if isinstance(n, ast.Name) and n.id in names and isinstance(n.ctx, ast.Load)]
        for n in loads:
            if _held(n, parent, defined):
                return node
        if loads:
            last_load = max(n.lineno for n in loads)
            loops = [n for n in ast.walk(scope) if isinstance(n, (ast.For, ast.AsyncFor, ast.While))]
            for n in ast.walk(scope):
                if getattr(n, 'lineno', 0) < p.lineno or not (_direct_mutation(n) or (isinstance(n, ast.Call) and _callee(n) in bad)):
                    continue
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) \
                        and n.func.value.id in names:
                    continue                    # a method called on the view itself changes no dict (it raises)
                if n.lineno <= last_load or start < p.lineno:
                    return node
                if any(l.lineno <= n.lineno <= l.end_lineno and any(l.lineno <= x.lineno <= l.end_lineno for x in loads)
                       for l in loops):
                    return node
    return None


def escape(tree):
    kept = stored(tree)
    if kept is not None:
        kept._ail_kept = True
        return kept
    parent = _parents(tree)
    names = set()
    changed = True
    while changed:                      # a name that holds a view: `ks = d.keys()`, `ks2 = ks`
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and _is_view(node.value, names):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id not in names:
                        names.add(t.id)
                        changed = True
            elif isinstance(node, ast.AnnAssign) and node.value is not None and _is_view(node.value, names):
                if isinstance(node.target, ast.Name) and node.target.id not in names:
                    names.add(node.target.id)
                    changed = True
    for node in ast.walk(tree):
        if not _is_view(node, names):
            continue
        p = parent.get(node)
        if isinstance(p, ast.Assign) and p.value is node and all(isinstance(t, ast.Name) for t in p.targets):
            continue
        if isinstance(p, ast.AnnAssign) and p.value is node and isinstance(p.target, ast.Name):
            continue
        if not _walks(node, parent):
            return node
    return None


def refusal(node):
    if getattr(node, '_ail_kept', False):
        return kept_refusal(node)
    what = node.id if isinstance(node, ast.Name) else node.func.attr + '()'
    kind = 'a dict view' if isinstance(node, ast.Name) else 'dict.%s' % node.func.attr
    return ('%s used as a value (line %d): the typed path holds `%s` as a list and would print, compare or combine a list; '
            'dict views (`dict_keys([...])`, `d.keys() & s`, `d.keys() == s`) are on the general path'
            % (kind, getattr(node, 'lineno', 0), what))


def kept_refusal(node):
    return ('a dict view kept in a name, field, item or container (`x = d.%s()`, line %d): a view follows its dict in '
            'CPython, but here it is a snapshot, so it would show old contents and a loop over it would not raise '
            '"dictionary changed size during iteration"; call `d.%s()` where it is used, or keep `list(d.%s())` '
            'for a snapshot' % (node.func.attr, getattr(node, 'lineno', 0), node.func.attr, node.func.attr))


# ---- ordering of views (C109): `d.keys() < s`, `<=`, `>`, `>=` -----------------------------------------------------------
# Only a program that has a view call and an ordering comparison gets this (build() in pyboxed2), so the C of every other
# program stays as it was.
_CMP_PROTO = ('static inline ail_st ail__view_cmp(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, int op);\n')
_CMP_BODY = r'''/* `<` `<=` `>` `>=` with a dict view: a keys or items view and a set, frozenset or keys / items view compare as sets (the
   subset test); anything else (a values view, a list, ...) is CPython's TypeError naming the operator and both types */
static inline int ail__view_n(ail_obj x) { return AIL_IS_ANYSET(x.tag) ? (int)AIL_SETOBJ(x)->used : (int)((ail_vecobj *)x.o)->n; }
static inline ail_st ail__view_has(ail_ctx *cx, int *f, ail_obj y, ail_obj key) {
    if (AIL_IS_ANYSET(y.tag)) return ail_setx_contains_key(cx, f, AIL_SETOBJ(y), key);
    const ail_vecobj *vy = (const ail_vecobj *)y.o;
    *f = 0;
    for (int64_t j = 0; j < vy->n && !*f; j++) *f = ail_member_eq(key, vy->p[j]);
    return AIL_OK;
}
static inline ail_st ail__view_within(ail_ctx *cx, int *res, ail_obj x, ail_obj y) {      /* every element of x is in y */
    int f = 1; ail_st st;
    *res = 1;
    if (AIL_IS_ANYSET(x.tag)) {
        const ail_setobj *so = AIL_SETOBJ(x);
        int64_t pos = 0; ail_setentry *e;
        while (*res && ail_setx_next(so, &pos, &e)) { st = ail__view_has(cx, &f, y, e->key); if (st != AIL_OK) return st; if (!f) *res = 0; }
        return AIL_OK;
    }
    const ail_vecobj *vx = (const ail_vecobj *)x.o;
    for (int64_t i = 0; i < vx->n && *res; i++) { st = ail__view_has(cx, &f, y, vx->p[i]); if (st != AIL_OK) return st; if (!f) *res = 0; }
    return AIL_OK;
}
static inline ail_st ail__view_cmp(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, int op) {
    int ka = ail__view_kind(a), kb = ail__view_kind(b);
    int a_s = ka == 1 || ka == 3 || AIL_IS_ANYSET(a.tag), b_s = kb == 1 || kb == 3 || AIL_IS_ANYSET(b.tag);
    if (!a_s || !b_s) {
        static const char *const sym[4] = { "<", "<=", ">", ">=" };
        char na[256], nb[256], eb[160];
        snprintf(na, sizeof na, "%s", ail__tname_c(a));
        snprintf(nb, sizeof nb, "%s", ail__tname_c(b));
        snprintf(eb, sizeof eb, "'%s' not supported between instances of '%s' and '%s'", sym[op], na, nb);
        return ail_raise_c(cx, AIL_B_TYPEERROR, eb);
    }
    int na = ail__view_n(a), nb = ail__view_n(b), r = 0; ail_st st;
    if (op < 2) { if (op == 0 ? na < nb : na <= nb) { st = ail__view_within(cx, &r, a, b); if (st != AIL_OK) return st; } }
    else if (op == 2 ? na > nb : na >= nb) { st = ail__view_within(cx, &r, b, a); if (st != AIL_OK) return st; }
    *out = ail_box_bool(r); return AIL_OK;
}
'''


def wants_compare(source):
    """A program with an ordering comparison (`<`, `<=`, `>`, `>=`) and a view that can reach it needs `patch_compare`: a
    comparison with a view call or a name holding one as an operand, or a view that is kept, handed to a function of the
    program, returned or put in a field, an item or a display (`_held`)."""
    if not any(w in source for w in ('.keys()', '.values()', '.items()')):
        return False
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return False
    ordering = [n for n in ast.walk(tree) if isinstance(n, ast.Compare)
                and any(isinstance(o, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for o in n.ops)]
    if not ordering:
        return False
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and _is_view(n.value, names):
            names.update(t.id for t in n.targets if isinstance(t, ast.Name))
    for c in ordering:
        if any(_is_view(x, names) for x in [c.left] + c.comparators):
            return True
    parent = _parents(tree)
    defined = _mutating_functions(tree)[1]
    return any(_is_view(n, names) and _held(n, parent, defined) for n in ast.walk(tree))


def patch_compare(c_text):
    mark = '/* an order-free hash of the elements, so equal frozensets hash alike */'
    if c_text.count(mark) != 1:
        raise AssertionError('dictviews: no place for the view comparison')
    first = 'static inline ail_st ail_op_lt(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {'
    if c_text.count(first) != 1:
        raise AssertionError('dictviews: no ail_op_lt')
    c_text = c_text.replace(first, _CMP_PROTO + first, 1)
    c_text = c_text.replace(mark, _CMP_BODY + mark, 1)
    for i, name in enumerate(('lt', 'le', 'gt', 'ge')):
        head = 'static inline ail_st ail_op_%s(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) { ' % name
        if c_text.count(head) != 1:
            raise AssertionError('dictviews: no ail_op_' + name)
        c_text = c_text.replace(head, head + 'if (__builtin_expect(ail__view_kind(a) || ail__view_kind(b), 0)) return ail__view_cmp(cx, out, a, b, %d); ' % i, 1)
    return c_text
