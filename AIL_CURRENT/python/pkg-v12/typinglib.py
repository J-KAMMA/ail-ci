"""typing runtime names that are lowered to ordinary Python (called from stdlib5).

* `TypedDict` class and functional declarations become plain dicts: every use of the declared name is read as
  `dict`, the declaration itself is dropped.  A TypedDict is a dict at run time in CPython, and the fields are not
  checked, so a literal, `Movie(title=...)`, `Movie(**data)`, item access and `len` keep CPython's behaviour.
* `NewType("Name", Base)` is `Base` at run time: every use of the declared name is read as the base type, and the
  declaration is dropped.  The programs keep the calls (`UserId(7)`), which become `int(7)`.
* `cast(T, value)` returns `value`; the type expression is not evaluated (it has no run-time effect in CPython).

Only the names in HANDLED are taken out of `from typing import ...`; the other typing names stay for the ordinary
annotation handling.  `import typing` is left in place (an unused one is harmless).
"""
import ast
import copy

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
    def __init__(self, binder, typed_dicts, new_types):
        self.binder = binder
        self.typed_dicts = typed_dicts
        self.new_types = new_types

    def visit_Call(self, node):
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
                return ast.copy_location(copy.deepcopy(self.new_types[node.id]), node)
        return node


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
    tree.body = [_Fix(binder, typed_dicts, new_types).visit(stmt) for stmt in tree.body]
