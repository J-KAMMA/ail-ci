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

from . import effects as E                 # rc3: the effect vocabulary and summaries

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
# returned or captured, and the object it points to is kept alive by the owner it was read
# from: while the cursor is live that owner is not written, and no call may write it.
#
# The keep-alive half is the effect summary of `ir/effects.py`, computed here on the source
# AST because this runs before lowering.  Locations use the same vocabulary: `Field(?,f)`
# is a field store (the class is unknown this early, so every class's field `f` is conflated
# -- that only makes the proof stronger), `Elem(root)`/`Spine(root)` are a list write.  A
# call is charged the callee's summary (a fixed point over the module's functions); an
# unknown callee is `Effects(unknown=True)` and keeps every cursor owning.
#
# Liveness is path sensitive: a write counts only when the cursor is bound on some path to
# it.  A loop whose body binds the cursor makes its whole body (and its test, re-evaluated
# on later iterations) live.  Under these conditions the cursor needs no reference: no
# retain on entry, no store retain/release, no release at exit.
# ---------------------------------------------------------------------------

def _deepest_name(node):
    """The root local of a field/element path (`a.b[i].c` -> 'a'), or None."""
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _nodes(root):
    """Every node under `root`, without descending into a nested function or class: those
    have their own summary (a call to one reaches it) and a closure is refused outright."""
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.Lambda, ast.ClassDef)):
                continue
            stack.append(child)


def _structure_ok(fn):
    """Refusals no keep-alive proof can recover: a `del`, a global/nonlocal cell, a closure,
    a `with`, or a loop target that is not a plain name."""
    for node in ast.walk(fn):
        if isinstance(node, (ast.Delete, ast.Global, ast.Nonlocal)):
            return False
        if node is not fn and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                ast.Lambda, ast.ClassDef)):
            return False
        if isinstance(node, (ast.With, ast.AsyncWith)):
            return False
        if isinstance(node, (ast.For, ast.AsyncFor)) and not isinstance(node.target, ast.Name):
            return False
    return True


def _call_effects(node, summaries, classes):
    """The write effects of one call: a read-only builtin writes nothing; a class constructor
    writes only a fresh heap object; a module function is its fixed-point summary; anything
    else may write anything."""
    f = node.func
    if isinstance(f, ast.Name):
        if f.id in READ_ONLY_CALLS:
            return E.NONE
        if f.id in classes:
            return E.Effects(allocs=['Heap'])
        if f.id in summaries:
            return summaries[f.id]
    elif isinstance(f, ast.Attribute) and f.attr in summaries:
        return summaries[f.attr]
    return E.UNKNOWN


def _ast_effects(fn, summaries, classes):
    """The write half of `fn`'s `ir/effects.py` summary, on the source AST."""
    writes = set()
    unknown = False
    for node in _nodes(fn):
        if isinstance(node, (ast.Delete, ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith)):
            unknown = True
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            writes.add('Field(?,%s)' % node.attr)
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            root = _deepest_name(node.value) or '?'
            writes.add('Elem(%s)' % root)
            writes.add('Spine(%s)' % root)
        elif isinstance(node, ast.Call):
            eff = _call_effects(node, summaries, classes)
            writes |= eff.writes
            unknown = unknown or eff.unknown
    return E.Effects(writes=writes, unknown=unknown)


def _summaries(fns, classes):
    """Write summaries of every module function, iterated to a fixed point over calls (the
    same shape as `effects.summarize_program`).  Same-named functions are merged by union:
    the callee cannot be told apart, so the stronger summary is the sound one."""
    groups = {}
    for f in fns:
        groups.setdefault(f.name, []).append(f)
    out = {name: E.NONE for name in groups}
    changed = True
    while changed:
        changed = False
        for name, fs in groups.items():
            eff = E.NONE
            for f in fs:
                eff = eff | _ast_effects(f, out, classes)
            if eff != out[name]:
                out[name] = eff
                changed = True
    return out


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


def _loop_bound(fn):
    """Names bound anywhere inside a loop (its target or a store in the body).  The emitter
    releases such a local at the loop point, so it cannot be the root a cursor outlives."""
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            for sub in _nodes(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    names.add(sub.id)
    return names


def _roots_ok(name, candidates, cursors, params, stores, loop_bound, seen=None):
    """Every chain a cursor name can be reached from starts at a parameter or a local that is
    bound exactly once, outside any loop (so nothing can replace or release it while the cursor
    lives)."""
    if name in params:
        return True
    seen = set() if seen is None else seen
    if name in seen:
        return True
    seen.add(name)
    found = False

    def root_ok(base):
        return base in params or (stores.get(base, 0) == 1 and base not in loop_bound)

    for kind, source in candidates.get(name, ()):
        if kind in ('field', 'elem', 'for'):
            base = _base_of(kind, source)
            if base is None:
                return False
            if base == name or base in seen:
                continue
            if base in cursors:
                if not _roots_ok(base, candidates, cursors, params, stores, loop_bound, seen):
                    return False
                found = True
            elif root_ok(base):
                found = True
            else:
                return False
        elif kind == 'name':
            if source == name or source in seen:
                continue
            if source in cursors:
                if not _roots_ok(source, candidates, cursors, params, stores, loop_bound, seen):
                    return False
                found = True
            elif root_ok(source):
                found = True
            else:
                return False
        else:
            return False
    return found


def _call_borrows(call, node, borrowed, by_name, classes):
    """Whether `node`, passed directly to `call`, sits in a position the callee borrows.

    A read-only builtin reads every argument; a module function borrows exactly the positions
    rc2 proved read-only, so it neither stores nor returns the cursor; a constructor stores its
    arguments into a fresh object."""
    f = call.func
    if isinstance(f, ast.Name):
        if f.id in READ_ONLY_CALLS:
            return True
        if f.id in classes:
            return False
        name, shift = f.id, 0
    elif isinstance(f, ast.Attribute):
        name, shift = f.attr, 1                # the receiver is the callee's `self`
    else:
        return False
    if name not in borrowed or name not in by_name:
        return False
    order = param_names(by_name[name])
    for i, arg in enumerate(call.args):
        if arg is node:
            return shift + i < len(order) and order[shift + i] in borrowed[name]
    for kw in call.keywords:
        if kw.value is node:
            return kw.arg is not None and kw.arg in borrowed[name]
    return False


def _receiver_borrows(call, borrowed, by_name):
    """Whether the method `call` names borrows its receiver (`self`), so calling it on the
    cursor neither stores nor returns the cursor."""
    f = call.func
    if not isinstance(f, ast.Attribute):
        return False
    name = f.attr
    if name not in borrowed or name not in by_name:
        return False
    order = param_names(by_name[name])
    return bool(order) and order[0] in borrowed[name]


def _loads_ok(fn, name, borrowed, by_name, classes):
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
            grand = parents.get(parent)
            if isinstance(grand, ast.Call) and grand.func is parent:
                if _receiver_borrows(grand, borrowed, by_name):
                    continue                            # n.m() with a borrowed receiver
                return False
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
            targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
            if all(isinstance(t, ast.Name) for t in targets):
                continue                                # m = n (m is a cursor)
            return False                                # stored into a field or an element
        if isinstance(parent, ast.Call) and _call_borrows(parent, node, borrowed, by_name, classes):
            continue                                    # len(n) / print(n) / a read-only callee
        if isinstance(parent, ast.IfExp) and parent.test is node:
            continue
        return False
    return True


def _protected(name, candidates):
    """The locations a write can release the chain through: the field names the cursor is read
    through, and (for an element or iteration source) every list write -- this early a second
    name for the same list cannot be told apart, so any list write counts."""
    fields, elem = set(), False
    for kind, source in candidates.get(name, ()):
        if kind == 'field':
            fields.add(source.attr)
        elif kind in ('elem', 'for'):
            elem = True
    return fields, elem


def _writes_hit(writes, unknown, fields, elem):
    if unknown:
        return True
    for loc in writes:
        if loc.startswith('Field(?,'):
            if loc[8:-1] in fields:
                return True
        elif loc.startswith('Elem(') or loc.startswith('Spine('):
            if elem:
                return True
    return False


def _live_refuses(fn, name, fields, elem, summaries, classes):
    """Whether a write that may release the chain can run while `name` is live.

    A forward walk carries "bound on some path so far".  A loop whose body can bind the name
    makes its whole body live (iteration two executes it with the cursor bound) and its test
    too; the iterable of a `for` is evaluated once, before the body, so it uses the state on
    entry."""
    def danger(node):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                eff = _call_effects(sub, summaries, classes)
                if _writes_hit(eff.writes, eff.unknown, fields, elem):
                    return True
            elif isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Store):
                if sub.attr in fields:
                    return True
            elif isinstance(sub, ast.Subscript) and isinstance(sub.ctx, ast.Store):
                if elem:
                    return True
            elif isinstance(sub, ast.Delete):
                return True
        return False

    def binds(stmts):
        for st in stmts:
            for sub in _nodes(st):
                if isinstance(sub, ast.Name) and sub.id == name \
                        and isinstance(sub.ctx, (ast.Store, ast.Del)):
                    return True
        return False

    def seq(stmts, live):
        for st in stmts:
            refused, live = one(st, live)
            if refused:
                return True, live
        return False, live

    def one(st, live):
        if isinstance(st, ast.If):
            if danger(st.test):
                return True, live
            r, l1 = seq(st.body, live)
            if r:
                return True, live
            r, l2 = seq(st.orelse, live)
            if r:
                return True, live
            return False, live or l1 or l2
        if isinstance(st, ast.While):
            loop = live or binds(st.body)
            if loop and danger(st.test):
                return True, live
            r, l = seq(st.body, loop)
            if r:
                return True, live
            return False, loop or l
        if isinstance(st, (ast.For, ast.AsyncFor)):
            if live and danger(st.iter):
                return True, live
            mine = isinstance(st.target, ast.Name) and st.target.id == name
            r, l = seq(st.body, live or mine or binds(st.body))
            if r:
                return True, live
            return False, live or mine or l
        if isinstance(st, ast.Try) or (getattr(ast, 'TryStar', None) is not None
                                       and isinstance(st, ast.TryStar)):
            r, l = seq(st.body, live)
            if r:
                return True, live
            after = live or l
            for h in st.handlers:
                r, lh = seq(h.body, after)
                if r:
                    return True, live
                after = after or lh
            r, l2 = seq(st.orelse, after)
            if r:
                return True, live
            after = after or l2
            # `finally` runs after the body, every handler and `else`, so it inherits their
            # liveness: a cursor bound in the body is still live when the cleanup writes.
            r, l3 = seq(st.finalbody, after)
            if r:
                return True, live
            return False, after or l3
        if isinstance(st, (ast.With, ast.AsyncWith)):
            return True, live                     # `_structure_ok` already refuses it
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False, live
        if live and danger(st):
            return True, live
        if any(isinstance(sub, ast.Name) and sub.id == name
               and isinstance(sub.ctx, ast.Store) for sub in _nodes(st)):
            return False, True
        return False, live

    return seq(fn.body, False)[0]


def _cursors_in(fn, borrowed, summaries, classes, by_name):
    """`borrowed` is rc2's whole map: this function's own positions come from its name, and a
    call to another module function borrows the positions recorded for that callee."""
    if not _structure_ok(fn):
        return set()
    candidates = _bindings(fn)
    stores = _store_counts(fn)
    params = set(param_names(fn))
    loop_bound = _loop_bound(fn)
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
            if not ok or not _loads_ok(fn, name, borrowed, by_name, classes):
                continue
            fields, elem = _protected(name, candidates)
            if _live_refuses(fn, name, fields, elem, summaries, classes):
                continue
            if _roots_ok(name, candidates, cursors, params, stores, loop_bound):
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
    fns = _functions(tree)
    classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    groups = {}
    for fn in fns:
        groups.setdefault(fn.name, []).append(fn)
    by_name = {k: v[0] for k, v in groups.items() if len(v) == 1}
    summaries = _summaries(fns, classes)
    out = {}
    for name, fs in groups.items():
        if len(fs) != 1:
            continue
        found = _cursors_in(fs[0], borrowed, summaries, classes, by_name)
        if found:
            out[name] = frozenset(found)
    return out
