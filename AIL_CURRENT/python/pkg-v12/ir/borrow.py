"""Borrow inference for typed-function parameters (rc2: read-only parameters).

A parameter of a typed function is *borrowed* when, on every path of the callee, it is only
read: never stored into a field, list, dict, global or closure, never returned, never rebound,
and never passed to a callee position that is not itself borrowed.  A borrowed parameter takes
no retain on entry and no release on exit; the caller keeps its reference alive across the call
(it already holds one), so Python sharing is unchanged: no copy is made and no object is freed
earlier than before.

Recursion is a fixpoint over the call graph, starting from "all borrowed" and demoting: a call
to a parameter position that has been demoted demotes the argument.

`AIL_RC_BORROW=0` turns the elision off entirely (the A/B switch and the escape hatch).
"""
import ast
import os

#: Calls whose arguments are only read -- no reference is stored, taken or handed on.
READ_ONLY_CALLS = frozenset(['abs', 'bool', 'float', 'id', 'int', 'isinstance', 'len', 'print',
                             'repr', 'round', 'str', 'type'])


def enabled():
    """Whether borrow elision is on (`AIL_RC_BORROW=0` is the A/B switch and escape hatch)."""
    return os.environ.get('AIL_RC_BORROW', '1') != '0'


def param_names(fn):
    """Every parameter name of `fn`, in source order."""
    a = fn.args
    names = [p.arg for p in list(a.posonlyargs) + list(a.args)]
    if a.vararg is not None:
        names.append(a.vararg.arg)
    names += [p.arg for p in a.kwonlyargs]
    if a.kwarg is not None:
        names.append(a.kwarg.arg)
    return names


def _aliases(node, names):
    """The parameter names `node` hands on as an object reference: a bare name, or one held in a
    container literal.  A field or element (`p.next`, `xs[i]`) is a different object with its own
    reference, so it is not an alias of `p` and needs no demotion."""
    if isinstance(node, ast.Name):
        return {node.id} & names
    if isinstance(node, ast.Starred):
        return _aliases(node.value, names)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        out = set()
        for e in node.elts:
            out |= _aliases(e, names)
        return out
    if isinstance(node, ast.Dict):
        out = set()
        for k, v in zip(node.keys, node.values):
            if k is not None:
                out |= _aliases(k, names)
            out |= _aliases(v, names)
        return out
    if isinstance(node, ast.IfExp):
        return _aliases(node.body, names) | _aliases(node.orelse, names)
    if isinstance(node, ast.BoolOp):
        out = set()
        for e in node.values:
            out |= _aliases(e, names)
        return out
    return set()


def _demoted(fn, names, borrowed_of, fn_of):
    """The parameter names of `fn` the rule refuses, given the callee borrow sets so far."""
    demoted = set()

    def note(node):
        demoted.update(_aliases(node, names))

    def call(node):
        f = node.func
        if isinstance(f, ast.Name) and f.id in READ_ONLY_CALLS:
            return
        if isinstance(f, ast.Name) and f.id in fn_of:
            order = param_names(fn_of[f.id])
            callee = borrowed_of[f.id]
            for i, arg in enumerate(node.args):
                if isinstance(arg, ast.Starred) or i >= len(order):
                    note(arg)
                elif _aliases(arg, names):
                    if order[i] not in callee:
                        note(arg)
            for kw in node.keywords:
                if kw.arg is None or kw.arg not in order:
                    note(kw.value)
                elif _aliases(kw.value, names) and kw.arg not in callee:
                    note(kw.value)
            return
        # a builtin, a class constructor, a method or a value: every argument takes its own
        # reference or stores it, so an argument that is (or holds) a parameter is not read-only
        for arg in node.args:
            note(arg)
        for kw in node.keywords:
            note(kw.value)

    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            if node.id in names:
                demoted.add(node.id)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            demoted.update(set(node.names) & names)
        elif isinstance(node, ast.Return):
            if node.value is not None:
                note(node.value)
        elif isinstance(node, (ast.Yield, ast.YieldFrom)):
            if node.value is not None:
                note(node.value)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, (ast.Attribute, ast.Subscript)):
                    note(node.value)      # stored into a field, list, dict or global cell
                else:
                    note(node.value)      # rebound, or aliased/unpacked into a new name
        elif isinstance(node, ast.AnnAssign):
            if node.value is not None:
                note(node.value)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, (ast.Attribute, ast.Subscript)):
                note(node.value)
        elif isinstance(node, ast.Call):
            call(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            if node is not fn:
                # a closure: any read of the parameter inside it captures the reference
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Name) and inner.id in names:
                        demoted.add(inner.id)
    return demoted


def analyze(tree, library=False, entries=()):
    """`{function name: frozenset(borrowed parameter names)}` for one module's typed functions."""
    if library:
        return {}
    fns = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    by_name = {f.name: f for f in fns}
    # a function used as a value can be called from a context this analysis cannot see, so its
    # parameters stay owned (the caller may hand it a transient reference)
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    as_value = {n.id for n in ast.walk(tree)
                if isinstance(n, ast.Name) and n.id in by_name and id(n) not in called}
    owned = set(entries) | {'main'} | as_value
    borrowed = {f.name: set() if f.name in owned else set(param_names(f)) for f in fns}
    changed = True
    while changed:
        changed = False
        for f in fns:
            if f.name in owned or not borrowed[f.name]:
                continue
            keep = borrowed[f.name] - _demoted(f, set(param_names(f)), borrowed, by_name)
            if keep != borrowed[f.name]:
                borrowed[f.name] = keep
                changed = True
    return {k: frozenset(v) for k, v in borrowed.items() if v}
