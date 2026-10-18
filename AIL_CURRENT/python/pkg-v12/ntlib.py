"""collections.namedtuple, typing.NamedTuple and collections.ChainMap (library batch 5, called from stdlib5).

A named tuple becomes a class deriving from `_AilNT` (prelude_nt.py), generated from the field list:

    Point = namedtuple("Point", "x y")          -> class Point(_AilNT): __init__, _ail_vals, __repr__, _asdict, _replace
    class P(NamedTuple): x: int; y: int = 0      -> the same, with defaults and the class's methods
    class P(namedtuple("P", "x y")): def f(..)   -> the same, with the methods

The result indexes, iterates (unpacking, for loops), compares with tuples and with other named tuples, hashes,
prints as `Point(x=1, y=2)`, `p._asdict()`, `p._replace(x=3)`, `P._make(xs)`, `P._fields`. Fields carry no types here
(annotations of a NamedTuple class are dropped). Not built, refused by name: `rename=True`, `module=`, field names
that are not literals, `__new__`, class attributes, `_field_defaults`, `typing.NamedTuple("P", [...])`.
Differences: `isinstance(p, tuple)` is False, slices `p[1:]` are not built.

`ChainMap(m1, m2, ...)` is the class of prelude_chainmap.py: item lookup through the maps in order, writes to the
first, `get`, `in`, `len`, iteration in CPython's order, `keys values items`, `new_child`, `.parents`, `maps`, `update`,
`setdefault`, `pop`, `clear`, `copy`, `repr`.
"""
import ast
import re

import stdlib5
from stdlib4 import refuse


class Spec:
    def __init__(self, var, typename, fields, defaults, methods):
        self.var = var                  # the class name in the program
        self.typename = typename        # the name printed by repr
        self.fields = fields
        self.defaults = defaults        # field -> expression node
        self.methods = methods          # FunctionDef nodes of the class body


def field_names(node, where):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        names = [n for n in re.split(r'[\s,]+', node.value) if n]
    elif isinstance(node, (ast.List, ast.Tuple)) and all(
            isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
        names = [e.value for e in node.elts]
    else:
        refuse(where, 'namedtuple: the field names must be a string literal ("x y" or "x, y") or a list of string literals')
    for n in names:
        if not n.isidentifier() or n.startswith('_'):
            refuse(where, 'namedtuple: the field name %r is not a plain identifier (a leading underscore is refused too)' % n)
    if len(set(names)) != len(names):
        refuse(where, 'namedtuple: duplicate field names')
    return names


def spec_from_call(call, var, cb, methods):
    if len(call.args) != 2:
        refuse(call, 'namedtuple(typename, field_names) takes two arguments here')
    if not (isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)):
        refuse(call, 'namedtuple: the type name must be a string literal')
    fields = field_names(call.args[1], call)
    defaults = {}
    for kw in call.keywords:
        if kw.arg == 'defaults':
            if not isinstance(kw.value, (ast.List, ast.Tuple)):
                refuse(call, 'namedtuple: defaults= must be a list or tuple display')
            vals = list(kw.value.elts)
            if len(vals) > len(fields):
                refuse(call, 'namedtuple: more defaults than fields')
            for field, val in zip(fields[len(fields) - len(vals):], vals):
                defaults[field] = val
        elif kw.arg == 'module':
            continue
        else:
            refuse(call, 'namedtuple: %s= is not built' % kw.arg)
    return Spec(var, call.args[0].value, fields, defaults, methods)


def class_methods(cls, what):
    methods = []
    for item in cls.body:
        if isinstance(item, ast.FunctionDef):
            if item.name == '__new__':
                refuse(item, '%s: __new__ is not built' % what)
            if item.decorator_list:
                for dec in item.decorator_list:
                    if not (isinstance(dec, ast.Name) and dec.id == 'staticmethod'):
                        refuse(dec, '%s: the decorator on %s is not built' % (what, item.name))
            methods.append(item)
        elif isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
            continue
        elif isinstance(item, ast.Pass):
            continue
        elif isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name) \
                and item.targets[0].id == '__slots__':
            continue
        elif isinstance(item, ast.AnnAssign):
            continue                                   # a NamedTuple field: handled by the caller
        else:
            refuse(item, '%s: a class attribute is not built; keep it at module level' % what)
    return methods


def spec_from_class(cls, tb):
    methods = class_methods(cls, 'NamedTuple class %s' % cls.name)
    fields, defaults = [], {}
    for item in cls.body:
        if isinstance(item, ast.AnnAssign):
            if not isinstance(item.target, ast.Name) or item.target.id.startswith('_'):
                refuse(item, 'NamedTuple class %s: a field must be a plain name' % cls.name)
            fields.append(item.target.id)
            if item.value is not None:
                defaults[item.target.id] = item.value
            elif defaults:
                refuse(item, 'NamedTuple class %s: a field without a default follows a field with one' % cls.name)
    return Spec(cls.name, cls.name, fields, defaults, methods)


def generate(spec, user_defined):
    f = spec.fields
    params = ''.join(', %s%s' % (n, (' = ' + ast.unparse(spec.defaults[n])) if n in spec.defaults else '') for n in f)
    lines = ['class %s(_AilNT):' % spec.var, '    def __init__(self%s):' % params]
    lines += ['        self.%s = %s' % (n, n) for n in f] or ['        pass']
    lines += ['    def _ail_vals(self) -> list:', '        return [%s]' % ', '.join('self.' + n for n in f)]
    lines += ['    def _ail_names(self) -> list:', '        return [%s]' % ', '.join(repr(n) for n in f)]
    lines += ['    def _ail_typename(self) -> str:', '        return %r' % spec.typename]
    lines += ['    def _ail_from(self, v: list):', '        return %s(%s)' % (spec.var, ', '.join('v[%d]' % i for i in range(len(f))))]
    cls = ast.parse('\n'.join(lines)).body[0]
    cls.body = [m for m in cls.body if not (isinstance(m, ast.FunctionDef) and m.name in user_defined)]
    cls.body.extend(spec.methods)
    return cls


def make_function(spec):
    n = len(spec.fields)
    return ast.parse(
        'def _ail_nt_%s_make(it):\n    v = list(it)\n    if len(v) != %d:\n'
        '        raise TypeError("Expected %d arguments, got " + str(len(v)))\n    return %s(%s)\n'
        % (spec.var, n, n, spec.var, ', '.join('v[%d]' % i for i in range(n)))).body[0]


def ordered_dict_object(tree, peek):
    """Whether the program keeps an OrderedDict where the typed collections pass does not build one: in an attribute
    (a class field) or in a variable at module level. Then every OrderedDict of the program is the class of
    prelude_ordereddict.py."""
    def is_od(value):
        return isinstance(value, ast.Call) and peek.attr(value.func) == 'OrderedDict'
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and is_od(node.value):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Attribute) for t in targets):
                return True
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and is_od(node.value):
            return True
    return False


def run(tree, text):
    peek = stdlib5.peek_imports(tree, 'collections')
    od_class = bool(peek) and ordered_dict_object(tree, peek)
    handled = {'namedtuple', 'ChainMap'} | ({'OrderedDict'} if od_class else set())
    cb = stdlib5.take_imports(tree, 'collections', handled, whole=False)
    tb = stdlib5.take_imports(tree, 'typing', {'NamedTuple'}, whole=False)
    if not cb and not tb:
        return
    specs = {}
    out = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name) \
                and isinstance(stmt.value, ast.Call) and cb.attr(stmt.value.func) == 'namedtuple':
            spec = spec_from_call(stmt.value, stmt.targets[0].id, cb, [])
            specs[spec.var] = spec
            cls = generate(spec, set())
            out.append(ast.copy_location(cls, stmt))
            continue
        if isinstance(stmt, ast.ClassDef) and stmt.bases:
            kinds = []
            for b in stmt.bases:
                if tb.attr(b) == 'NamedTuple':
                    kinds.append('typed')
                elif isinstance(b, ast.Call) and cb.attr(b.func) == 'namedtuple':
                    kinds.append('call')
                else:
                    kinds.append(None)
            if any(kinds):
                if len(stmt.bases) != 1 or stmt.keywords or stmt.decorator_list:
                    refuse(stmt, 'class %s: a named tuple class with other bases, keywords or decorators is not built' % stmt.name)
                if kinds[0] == 'typed':
                    spec = spec_from_class(stmt, tb)
                else:
                    spec = spec_from_call(stmt.bases[0], stmt.name, cb, class_methods(stmt, 'class %s' % stmt.name))
                specs[spec.var] = spec
                user = {m.name for m in spec.methods}
                out.append(ast.copy_location(generate(spec, user), stmt))
                continue
        out.append(stmt)
    tree.body = out
    used_make = set()
    chain = {'used': False, 'od': False}

    def fix(node):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in specs:
            spec = specs[node.value.id]
            if node.attr == '_make':
                used_make.add(spec.var)
                return stdlib5.name('_ail_nt_%s_make' % spec.var)
            if node.attr == '_fields':
                return ast.Tuple(elts=[ast.Constant(value=n) for n in spec.fields], ctx=ast.Load())
            if node.attr in ('_field_defaults', '_fields_defaults'):
                refuse(node, '%s: not built' % node.attr)
            return None
        if cb.attr(node) == 'ChainMap':
            chain['used'] = True
            return stdlib5.name('ChainMap')
        if od_class and cb.attr(node) == 'OrderedDict':
            chain['od'] = True
            return stdlib5.name('OrderedDict')
        return None
    tree.body = [stdlib5.Replace(fix).visit(s) for s in tree.body]
    cb.names.pop('ChainMap', None)
    cb.names.pop('OrderedDict', None)
    if chain['used']:
        for each in ast.walk(tree):
            if isinstance(each, ast.Attribute) and each.attr == 'parents' and isinstance(each.ctx, ast.Load):
                each.attr = '_ail_parents'
                # `cm.parents` -> `cm._ail_parents()`: wrap below
        tree.body = [ParentsCall().visit(s) for s in tree.body]
    # the helper functions go right after their classes
    final = []
    for stmt in tree.body:
        final.append(stmt)
        if isinstance(stmt, ast.ClassDef) and stmt.name in used_make:
            final.append(make_function(specs[stmt.name]))
    tree.body = final
    stdlib5.leftover(tree, cb, 'namedtuple("P", "x y") assigned at module level is built',
                     only={'namedtuple', 'ChainMap'} | ({'OrderedDict'} if od_class else set()))
    if tb.names:
        for each in ast.walk(tree):
            if isinstance(each, ast.Name) and each.id in tb.names:
                refuse(each, 'typing.NamedTuple is built only as a class base (class P(NamedTuple): x: int)')
    if specs:
        text.append(stdlib5.prelude('nt'))
    if chain['used']:
        text.append(stdlib5.prelude('chainmap'))
    if chain['od']:
        text.append(stdlib5.prelude('ordereddict'))


class ParentsCall(ast.NodeTransformer):
    def visit_Attribute(self, node):
        self.generic_visit(node)
        if node.attr == '_ail_parents' and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Call(func=node, args=[], keywords=[]), node)
        return node
