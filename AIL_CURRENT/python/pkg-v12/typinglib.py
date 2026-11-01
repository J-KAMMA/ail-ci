"""typing runtime names that are lowered to ordinary Python (called from stdlib5).

* `TypedDict` class and functional declarations become plain dicts: every use of the declared name is read as
  `dict`, the declaration itself is dropped.  A TypedDict is a dict at run time in CPython, and the fields are not
  checked, so a literal, `Movie(title=...)`, `Movie(**data)`, item access and `len` keep CPython's behaviour.
* `NewType("Name", Base)` keeps CPython's call behaviour: `Name(v)` is `v` itself (not `Base(v)`), and a call
  with another arity or with any keyword raises `TypeError` as `NewType.__call__` does.  A use of the name that is
  not a direct call reads as an identity function of one argument (so an alias keeps working); the base, including
  a chain whose base is another NewType, is checked but not evaluated, and the declaration itself is dropped.
* `cast(T, value)` returns `value`; the type expression is not evaluated (it has no run-time effect in CPython).

Only the names in HANDLED are taken out of `from typing import ...`; the other typing names stay for the ordinary
annotation handling.  `import typing` is left in place (an unused one is harmless).
"""
import ast

import stdlib5
from stdlib4 import refuse

HANDLED = {'TypedDict', 'NewType', 'cast'}


def _typed_dict_call(call, binder):
    """The declared name of `X = TypedDict("X", fields)` / `X = typing.TypedDict(...)`, else None."""
    if not isinstance(call, ast.Call) or binder.attr(call.func) != 'TypedDict':
        return None
    if len(call.args) < 1 or len(call.args) > 2 or any(isinstance(a, ast.Starred) for a in call.args):
        refuse(call, 'TypedDict(typename, fields) takes the name and the fields here')
    name = call.args[0]
    if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
        refuse(call, 'TypedDict: the type name must be a string literal')
    return name.value


def _new_type_base(call, binder):
    """The base node of `X = NewType("X", Base)`, else None."""
    if not isinstance(call, ast.Call) or binder.attr(call.func) != 'NewType':
        return None
    if len(call.args) != 2 or call.keywords:
        refuse(call, 'NewType("Name", Base) takes two positional arguments here')
    name = call.args[0]
    if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
        refuse(call, 'NewType: the name must be a string literal')
    base = call.args[1]
    if not isinstance(base, (ast.Name, ast.Attribute)):
        refuse(call, 'NewType: the base type must be a name here')
    return base


class _Fix(ast.NodeTransformer):
    def __init__(self, binder, typed_dicts, new_types, ident, bad):
        self.binder = binder
        self.typed_dicts = typed_dicts
        self.new_types = new_types
        self.ident = ident
        self.bad = bad
        self.ident_used = False
        self.bad_used = False

    def visit_Call(self, node):
        is_new_type = isinstance(node.func, ast.Name) and node.func.id in self.new_types
        if is_new_type:
            node.args = [self.visit(a) for a in node.args]
            for keyword in node.keywords:
                keyword.value = self.visit(keyword.value)
            if not node.keywords and len(node.args) == 1 and not isinstance(node.args[0], ast.Starred):
                return ast.copy_location(node.args[0], node)
            if not node.keywords and len(node.args) == 1:
                self.ident_used = True
                func = ast.Name(id=self.ident, ctx=ast.Load())
            else:
                self.bad_used = True
                func = ast.Name(id=self.bad, ctx=ast.Load())
                positional = ast.List(elts=node.args, ctx=ast.Load())
                keys = [ast.Constant(value=k.arg) if k.arg is not None else None for k in node.keywords]
                values = [k.value for k in node.keywords]
                return ast.copy_location(ast.Call(
                    func=func, args=[positional, ast.Dict(keys=keys, values=values)], keywords=[]), node)
            return ast.copy_location(ast.Call(func=func, args=node.args, keywords=[]), node)
        is_cast = self.binder.attr(node.func) == 'cast'
        is_typed_dict = isinstance(node.func, ast.Name) and node.func.id in self.typed_dicts
        self.generic_visit(node)
        if is_cast:
            if len(node.args) == 2 and not node.keywords:
                return ast.copy_location(node.args[1], node)
            refuse(node, 'cast(T, value) takes two positional arguments here')
        if (is_typed_dict and not node.args and len(node.keywords) == 1
                and node.keywords[0].arg is None):
            return ast.copy_location(ast.Call(func=ast.Name(id='dict', ctx=ast.Load()),
                                              args=[node.keywords[0].value], keywords=[]), node)
        return node

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            if node.id in self.typed_dicts:
                return ast.copy_location(ast.Name(id='dict', ctx=ast.Load()), node)
            if node.id in self.new_types:
                self.ident_used = True
                return ast.copy_location(ast.Name(id=self.ident, ctx=ast.Load()), node)
        return node


def _resolve(new_types):
    """Each NewType base with a NewType base replaced by that NewType's own (already resolved) base."""
    def resolve(name, seen):
        base = new_types[name]
        if isinstance(base, ast.Name) and base.id in new_types:
            if base.id in seen:
                refuse(base, 'NewType %s has a cyclic base' % name)
            return resolve(base.id, seen | {name})
        return base
    return {name: resolve(name, {name}) for name in new_types}


def _fresh(tree, stem):
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    name = stem
    n = 0
    while name in used:
        n += 1
        name = '%s_%d' % (stem, n)
    return name


def _defs(ident, bad, ident_used, bad_used):
    out = []
    if ident_used:
        out.append(ast.parse('def %s(obj):\n    return obj\n' % ident, mode='exec').body[0])
    if bad_used:
        out.append(ast.parse('def %s(positional, keywords):\n'
                             '    raise TypeError("NewType() takes exactly one positional argument")\n'
                             % bad, mode='exec').body[0])
    return out


def _insert_helpers(tree, nodes):
    body = tree.body
    i = 0
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and \
            isinstance(body[0].value.value, str):
        i = 1
    while i < len(body) and isinstance(body[i], ast.ImportFrom) and body[i].module == '__future__':
        i += 1
    body[i:i] = nodes


def run(tree, text):
    binder = stdlib5.take_imports(tree, 'typing', HANDLED, whole=False)
    if not binder:
        return
    typed_dicts = set()
    new_types = {}
    body = []
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef):
            bases = [b for b in stmt.bases]
            is_typed_dict = any(binder.attr(b) == 'TypedDict' or (
                isinstance(b, ast.Name) and b.id in typed_dicts) for b in bases)
            if is_typed_dict:
                if stmt.decorator_list or [k for k in stmt.keywords if k.arg != 'total']:
                    refuse(stmt, 'class %s: a TypedDict decorator or keyword other than total is not built'
                           % stmt.name)
                typed_dicts.add(stmt.name)
                continue
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            target = stmt.targets[0].id
            declared = _typed_dict_call(stmt.value, binder)
            if declared is not None:
                typed_dicts.add(target)
                continue
            base = _new_type_base(stmt.value, binder)
            if base is not None:
                new_types[target] = base
                continue
        body.append(stmt)
    tree.body = body
    new_types = _resolve(new_types)
    ident = _fresh(tree, '_ail_newtype_identity')
    bad = _fresh(tree, '_ail_newtype_bad_call')
    fix = _Fix(binder, typed_dicts, new_types, ident, bad)
    tree.body = [fix.visit(stmt) for stmt in tree.body]
    _insert_helpers(tree, _defs(ident, bad, fix.ident_used, fix.bad_used))
