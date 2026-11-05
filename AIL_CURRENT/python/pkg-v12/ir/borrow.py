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
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict,
                               ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            # A container literal stores its elements in a new object, whatever expression it
            # appears in (`for x in [p]`, an `if` test, ...), so an element that is (or holds) a
            # parameter is not read-only -- the IR refuses such a store.
            note(node)
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


# ---------------------------------------------------------------------------
# rc3: cursor inference for loop traversal variables
#
# A local is a *cursor* when every binding of it is a read out of another object (a field
# read `n = n.next`, an element read `n = xs[i]`, a `for` element), another cursor, or a
# parameter (which the caller keeps alive for the whole call).  It is never stored,
# returned or captured, and nothing in the function can release what it points at: no
# field store, no element store, no call except a read-only builtin.  Under those
# conditions the object is kept alive by the owner the cursor was read from, so the
# cursor itself needs no reference: no retain on entry, no store retain/release, no
# release at exit.
#
# The keep-alive half is deliberately whole-function and conservative.  A cursor that
# would need a path-sensitive proof (a write on another branch, a call that may write)
# is not inferred; the local stays owning, which is always correct.
# ---------------------------------------------------------------------------

def _deepest_name(node):
    """The root local of a field/element path (`a.b[i].c` -> 'a'), or None."""
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _cursor_function_safe(fn):
    """Whether nothing in `fn` can release an object a cursor points at: no field or
    element store, no call except a read-only builtin, no del/global/nonlocal, no closure."""
    for node in ast.walk(fn):
        if isinstance(node, (ast.Delete, ast.Global, ast.Nonlocal)):
            return False
        if node is not fn and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                 ast.Lambda, ast.ClassDef)):
            return False
        if isinstance(node, ast.Call):
            f = node.func
            if not (isinstance(f, ast.Name) and f.id in READ_ONLY_CALLS):
                return False
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, (ast.Attribute, ast.Subscript)) and isinstance(sub.ctx, ast.Store):
                        return False
        if isinstance(node, ast.With):
            return False
        if isinstance(node, ast.For) and not isinstance(node.target, ast.Name):
            return False
    return True


def _bindings(fn):
    """{name: [(kind, expression)]} for every simple binding statement of a name.

    kind is 'field' (attribute read), 'elem' (subscript read), 'for' (loop element) or
    'name' (another name)."""
    out = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out.setdefault(target.id, []).append(_source(node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None \
                and isinstance(node.target, ast.Name):
            out.setdefault(node.target.id, []).append(_source(node.value))
        elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            out.setdefault(node.target.id, []).append(('for', node.iter))
        elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
            out.setdefault(node.target.id, []).append(_source(node.value))
    return out


def _source(node):
    if isinstance(node, ast.Attribute):
        return ('field', node)
    if isinstance(node, ast.Subscript):
        return ('elem', node)
    if isinstance(node, ast.Name):
        return ('name', node.id)
    return ('bad', node)


def _store_counts(fn):
    counts = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            counts[node.id] = counts.get(node.id, 0) + 1
    return counts


def _base_of(kind, source):
    if kind == 'for':
        return _deepest_name(source)
    if kind in ('field', 'elem'):
        return _deepest_name(source.value)
    return None


def _roots_ok(name, candidates, cursors, params, stores, seen=None):
    """Every chain a cursor name can be reached from starts at a parameter or a local that is
    bound exactly once (so nothing can replace or release it while the cursor lives)."""
    if name in params:
        return True
    seen = set() if seen is None else seen
    if name in seen:
        return True
    seen.add(name)
    found = False
    for kind, source in candidates.get(name, ()):
        if kind in ('field', 'elem', 'for'):
            base = _base_of(kind, source)
            if base is None:
                return False
            if base == name or base in seen:
                continue
            if base in cursors:
                if not _roots_ok(base, candidates, cursors, params, stores, seen):
                    return False
                found = True
            elif base in params or stores.get(base, 0) == 1:
                found = True
            else:
                return False
        elif kind == 'name':
            if source == name or source in seen:
                continue
            if source in cursors:
                if not _roots_ok(source, candidates, cursors, params, stores, seen):
                    return False
                found = True
            elif source in params or stores.get(source, 0) == 1:
                found = True
            else:
                return False
        else:
            return False
    return found


def _loads_ok(fn, name):
    """Every read of the name is a read through it or a test, never a hand-off."""
    parents = {}
    for node in ast.walk(fn):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Name) and node.id == name
                and isinstance(node.ctx, ast.Load)):
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.Attribute) and parent.value is node:
            continue                                    # n.next / n.value
        if isinstance(parent, ast.Subscript) and parent.value is node:
            continue                                    # n.kids[i]
        if isinstance(parent, ast.Compare):
            continue                                    # n is not None
        if isinstance(parent, (ast.If, ast.While)) and parent.test is node:
            continue                                    # while n:
        if isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.Not):
            continue                                    # not n
        if isinstance(parent, ast.BoolOp):
            continue
        if isinstance(parent, (ast.Assign, ast.AnnAssign)) and parent.value is node:
            continue                                    # m = n (m is a cursor)
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) \
                and parent.func.id in READ_ONLY_CALLS:
            continue                                    # len(n) / print(n)
        if isinstance(parent, ast.IfExp) and parent.test is node:
            continue
        return False
    return True


def _cursors_in(fn, borrowed):
    if not _cursor_function_safe(fn):
        return set()
    candidates = _bindings(fn)
    stores = _store_counts(fn)
    params = set(param_names(fn))
    names = [n for n, sources in candidates.items()
             if stores.get(n, 0) == len(sources)
             and all(kind != 'bad' for kind, _ in sources)]
    cursors = set()
    changed = True
    while changed:
        changed = False
        for name in names:
            if name in cursors:
                continue
            ok = True
            for kind, source in candidates[name]:
                if kind in ('field', 'elem', 'for'):
                    continue
                if kind == 'name' and (source in cursors or source in params):
                    continue
                ok = False
                break
            if not ok or not _loads_ok(fn, name):
                continue
            if _roots_ok(name, candidates, cursors, params, stores):
                cursors.add(name)
                changed = True
    return cursors


def analyze_cursors(tree, borrowed=None, library=False):
    """`{function name: frozenset(cursor locals)}` for one module.

    `borrowed` is rc2's `analyze` result.  Same-named functions are ambiguous at the emit
    point, so no cursor is claimed for them."""
    if library:
        return {}
    borrowed = borrowed or {}
    groups = {}
    for fn in _functions(tree):
        groups.setdefault(fn.name, []).append(fn)
    out = {}
    for name, fns in groups.items():
        if len(fns) != 1:
            continue
        found = _cursors_in(fns[0], set(borrowed.get(name, ())))
        if found:
            out[name] = frozenset(found)
    return out
