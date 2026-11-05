"""Borrow inference for typed-function parameters (rc2: read-only parameters).

A parameter of a typed function is *borrowed* when, on every path of the callee, it is only
read: never stored into a field, list, dict, global or closure, never returned, never rebound,
and never passed to a callee position that is not itself borrowed.  A borrowed parameter takes
no retain on entry and no release on exit; the caller keeps its reference alive across the call
(it already holds one), so Python sharing is unchanged: no copy is made and no object is freed
earlier than before.

Recursion is a fixpoint over the call graph, starting from "all borrowed" and demoting: a call
to a parameter position that has been demoted demotes the argument.

Methods are analysed too (a class body is a scope): the receiver of a call through an attribute
is read (the callee's `self`), the arguments follow the same rule.  Two functions that share a
name cannot be told apart at the emit point (it keys by bare name), so their sets are merged by
intersection -- a parameter is borrowed only when every same-named function borrows it.

`AIL_RC_BORROW=0` turns the elision off entirely (the A/B switch and the escape hatch).
"""
import ast
import os

#: Calls whose arguments are only read -- no reference is stored, taken or handed on.  The
#: copying constructors (`bytes(x)`, `list(x)`, ...) read their argument and build a new object;
#: they never keep the argument's reference.
READ_ONLY_CALLS = frozenset([
    'abs', 'all', 'any', 'bool', 'bytearray', 'bytes', 'dict', 'enumerate', 'float',
    'format', 'frozenset', 'hash', 'id', 'int', 'isinstance', 'issubclass', 'iter', 'len',
    'list', 'max', 'min', 'next', 'print', 'range', 'repr', 'reversed', 'round', 'set',
    'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
])

_CONTAINERS = (ast.List, ast.Tuple, ast.Set)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


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
    container literal or comprehension.  The iterable of a comprehension (`for x in p`) is read;
    only the element/key/value expressions become part of the new container.  A field or element
    (`p.next`, `xs[i]`) is a different object with its own reference, so it is not an alias of
    `p` and needs no demotion."""
    if isinstance(node, ast.Name):
        return {node.id} & names
    if isinstance(node, ast.Starred):
        return _aliases(node.value, names)
    if isinstance(node, ast.NamedExpr):
        return _aliases(node.value, names)
    if isinstance(node, _CONTAINERS):
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
    if isinstance(node, ast.ListComp) or isinstance(node, ast.SetComp) \
            or isinstance(node, ast.GeneratorExp):
        return _aliases(node.elt, names)
    if isinstance(node, ast.DictComp):
        return _aliases(node.key, names) | _aliases(node.value, names)
    if isinstance(node, ast.IfExp):
        return _aliases(node.body, names) | _aliases(node.orelse, names)
    if isinstance(node, ast.BoolOp):
        out = set()
        for e in node.values:
            out |= _aliases(e, names)
        return out
    return set()


def _position(node, names, order, callee):
    """Demote the parameters `node` hands to a callee position `order[0]`, `order[1]`, ...: a
    position the callee borrows is read, every other position takes its own reference."""
    if isinstance(node, ast.Starred) or not order:
        return _aliases(node, names)
    return set() if order[0] in callee else _aliases(node, names)


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
                demoted.update(_position(arg, names, order[i:], callee))
            for kw in node.keywords:
                if kw.arg is None or kw.arg not in order:
                    note(kw.value)
                elif _aliases(kw.value, names) and kw.arg not in callee:
                    note(kw.value)
            return
        if isinstance(f, ast.Attribute) and f.attr in fn_of:
            # a call to a method this module defines: its receiver is `self`, which the emitter
            # keeps owned, so a parameter used as the receiver owns its reference too
            order = param_names(fn_of[f.attr])
            callee = borrowed_of[f.attr]
            if order and order[0] == 'self':
                note(f.value)
            for i, arg in enumerate(node.args):
                demoted.update(_position(arg, names, order[i + 1:], callee))
            for kw in node.keywords:
                if kw.arg is None or kw.arg not in order:
                    note(kw.value)
                elif _aliases(kw.value, names) and kw.arg not in callee:
                    note(kw.value)
            return
        # a builtin, a class constructor, a method or a value: every argument takes its own
        # reference or stores it, so an argument that is (or holds) a parameter is not read-only.
        # The receiver of an attribute call is read: the callee's `self` keeps it alive.
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
        elif isinstance(node, ast.ExceptHandler) and node.name in names:
            demoted.add(node.name)
        elif isinstance(node, ast.Return):
            if node.value is not None:
                note(node.value)
        elif isinstance(node, (ast.Yield, ast.YieldFrom)):
            if node.value is not None:
                note(node.value)
        elif isinstance(node, ast.Raise):
            if node.exc is not None:
                note(node.exc)
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


def _functions(tree):
    """Every function of the module: top-level definitions and the methods of its classes."""
    out = []

    def classes(body):
        for n in body:
            if isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out.append(m)
                classes(n.body)

    classes(tree.body)
    out += [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return out


def _used_as_value(tree, names):
    """Function names that occur anywhere except as the direct callee of a call."""
    called = {id(n.func) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    values = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in names and id(n) not in called:
            values.add(n.id)
    # a method reached through an attribute (`x.m`) that is not that call's callee may escape
    method_calls = {id(n.func) for n in ast.walk(tree)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and n.attr in names and id(n) not in method_calls:
            values.add(n.attr)
    return values


def analyze(tree, library=False, entries=()):
    """`{function name: frozenset(borrowed parameter names)}` for one module's typed functions.

    Same-named functions (a method and a top-level helper, or two methods) are merged by
    intersection: the emit point keys by name, so only a parameter every one of them borrows may
    be elided."""
    if library:
        return {}
    fns = _functions(tree)
    all_names = {f.name for f in fns}
    unique = {}
    for f in fns:
        if f.name in unique:
            unique[f.name] = None          # ambiguous: calls to it cannot be resolved
        else:
            unique[f.name] = f
    by_name = {k: v for k, v in unique.items() if v is not None}
    owned = set(entries) | {'main'} | _used_as_value(tree, all_names)
    borrowed = {}
    for f in fns:
        per = borrowed.setdefault(f.name, set(param_names(f)))
        per &= set(param_names(f))
        if f.name in owned:
            per.clear()
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
