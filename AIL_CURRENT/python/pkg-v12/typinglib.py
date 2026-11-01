"""typing runtime names that are lowered to ordinary Python (called from stdlib5).

* `TypedDict` class and functional declarations become plain dicts: every use of the declared name that resolves to
  the module-level declaration is read as `dict`, the declaration itself is dropped.  A TypedDict is a dict at run
  time in CPython, and the fields are not checked, so a literal, `Movie(title=...)`, `Movie(**data)`, item access
  and `len` keep CPython's behaviour.  A local variable, parameter or other binding with the same name shadows the
  declaration, exactly as it does in CPython.
* `NewType("Name", Base)` keeps CPython's call behaviour: `Name(v)` is `v` itself (not `Base(v)`), and a call
  with another arity or with any keyword raises CPython's `TypeError` text.  A use of the name that is not a
  direct call reads as an identity function of one argument (so an alias keeps working); the base, including
  a chain whose base is another NewType, is checked but not evaluated, and the declaration itself is dropped.
  A shadowing local/parameter is left alone, as for TypedDict.
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


class _Bindings(ast.NodeVisitor):
    """The names one scope binds (function, class or module), without descending into a nested scope."""

    def __init__(self):
        self.names = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_FunctionDef(self, node):
        self.names.add(node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.names.add(node.name)

    def visit_Lambda(self, node):
        pass

    def visit_Import(self, node):
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split('.')[0])

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name != '*':
                self.names.add(alias.asname or alias.name)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def _comprehension(self, node):
        for inner in ast.walk(node):
            if isinstance(inner, ast.NamedExpr) and isinstance(inner.target, ast.Name):
                self.names.add(inner.target.id)

    visit_ListComp = _comprehension
    visit_SetComp = _comprehension
    visit_DictComp = _comprehension
    visit_GeneratorExp = _comprehension


def _params(args):
    names = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def _function_locals(node):
    names = _params(node.args)
    collector = _Bindings()
    for stmt in (node.body if isinstance(node.body, list) else [node.body]):
        collector.visit(stmt)
    names |= collector.names
    return names


def _scope_locals(nodes):
    collector = _Bindings()
    for node in nodes:
        collector.visit(node)
    return collector.names


class _Fix(ast.NodeTransformer):
    def __init__(self, binder, typed_dicts, new_types, ident, bad):
        self.binder = binder
        self.typed_dicts = typed_dicts
        self.new_types = new_types
        self.ident = ident
        self.bad = bad
        self.ident_used = False
        self.bad_used = False
        self.scopes = []

    def _declared(self, name):
        return name in self.typed_dicts or name in self.new_types

    def _shadowed(self, name):
        if not self.scopes:
            return False
        kind, names = self.scopes[-1]
        if name in names:
            return True
        for kind, names in reversed(self.scopes[:-1]):
            if kind == 'class':
                continue
            if name in names:
                return True
        return False

    def _visit_scope(self, kind, locals_, nodes):
        self.scopes.append((kind, locals_))
        result = [self.visit(node) for node in nodes]
        self.scopes.pop()
        return result

    def visit_FunctionDef(self, node):
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args = self.visit(node.args)
        node.returns = self.visit(node.returns) if node.returns is not None else None
        node.body = self._visit_scope('function', _function_locals(node), node.body)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        node.args = self.visit(node.args)
        node.body = self._visit_scope('function', _function_locals(node), [node.body])[0]
        return node

    def visit_ClassDef(self, node):
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.bases = [self.visit(b) for b in node.bases]
        node.keywords = [self.visit(k) for k in node.keywords]
        node.body = self._visit_scope('class', _scope_locals(node.body), node.body)
        return node

    def _visit_comprehension(self, node):
        first = node.generators[0]
        first.iter = self.visit(first.iter)
        targets = set()
        for gen in node.generators:
            collector = _Bindings()
            collector.visit(gen.target)
            targets |= collector.names
        self.scopes.append(('function', targets))
        for i, gen in enumerate(node.generators):
            if i:
                gen.iter = self.visit(gen.iter)
            gen.ifs = [self.visit(cond) for cond in gen.ifs]
        if isinstance(node, ast.DictComp):
            node.key = self.visit(node.key)
            node.value = self.visit(node.value)
        else:
            node.elt = self.visit(node.elt)
        self.scopes.pop()
        return node

    visit_ListComp = _visit_comprehension
    visit_SetComp = _visit_comprehension
    visit_DictComp = _visit_comprehension
    visit_GeneratorExp = _visit_comprehension

    def visit_Global(self, node):
        for name in node.names:
            if self._declared(name):
                refuse(node, 'a global %s declaration is not lowered here' % name)
        return node

    def visit_Nonlocal(self, node):
        for name in node.names:
            if self._declared(name):
                refuse(node, 'a nonlocal %s declaration is not lowered here' % name)
        return node

    def visit_Call(self, node):
        name = node.func.id if isinstance(node.func, ast.Name) else None
        is_new_type = name in self.new_types and not self._shadowed(name)
        is_cast = self.binder.attr(node.func) == 'cast'
        is_typed_dict = name in self.typed_dicts and not self._shadowed(name)
        if is_new_type:
            node.args = [self.visit(a) for a in node.args]
            for keyword in node.keywords:
                keyword.value = self.visit(keyword.value)
            if not node.keywords and len(node.args) == 1 and not isinstance(node.args[0], ast.Starred):
                return ast.copy_location(node.args[0], node)
            self.bad_used = True
            func = ast.Name(id=self.bad, ctx=ast.Load())
            positional = ast.List(elts=node.args, ctx=ast.Load())
            keys = [ast.Constant(value=k.arg) if k.arg is not None else None for k in node.keywords]
            values = [k.value for k in node.keywords]
            return ast.copy_location(ast.Call(
                func=func, args=[positional, ast.Dict(keys=keys, values=values)], keywords=[]), node)
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
        if isinstance(node.ctx, ast.Load) and self._declared(node.id) and not self._shadowed(node.id):
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
        out.append(ast.parse(
            'def %s(positional, keywords):\n'
            '    if keywords:\n'
            '        raise TypeError("_typing._idfunc() takes no keyword arguments")\n'
            '    if len(positional) != 1:\n'
            '        raise TypeError("_typing._idfunc() takes exactly one argument (%%d given)" %% len(positional))\n'
            '    return positional[0]\n'
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
    declared = typed_dicts | set(new_types)
    rebound = _scope_locals(body) & declared
    if rebound:
        name = sorted(rebound)[0]
        refuse(tree.body[0] if tree.body else tree,
               'the typing name %s is also assigned at module level; this lowering needs it to name one declaration'
               % name)
    new_types = _resolve(new_types)
    ident = _fresh(tree, '_ail_newtype_identity')
    bad = _fresh(tree, '_ail_newtype_bad_call')
    fix = _Fix(binder, typed_dicts, new_types, ident, bad)
    tree.body = [fix.visit(stmt) for stmt in tree.body]
    _insert_helpers(tree, _defs(ident, bad, fix.ident_used, fix.bad_used))
