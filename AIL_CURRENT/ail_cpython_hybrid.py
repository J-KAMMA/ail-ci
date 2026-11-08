# -*- coding: utf-8 -*-
"""CPython hybrid builds (`ail build --cpython prog.py -o DIR`).

The prototype compiles the functions that the typed emitter can compile as a real CPython
extension module, and leaves the original Python module in place for everything else.  The
extension is loaded only by the generated copy of the program: a native call that cannot take its
arguments (an int outside int64, a bool where an int was hypothesised, a dict/tuple/None, ...) or
that reports an int64 overflow raises a private `Fallback` exception, and the Python wrapper calls
the original function.  This is deliberately behind an explicit flag; the default build is never
touched.

The unit of acceleration is a top-level function that `pymix.analyze` selects and `pyboxed2`'s
existing mixed-mode machinery accepts (the same candidates a standalone mixed-mode build wires).
Only the C ABI of that machinery is reused; no general-path executable is produced.

Design and the wider semantics are in docs/design/CPYTHON_HYBRID.md (AIL_CURRENT/docs/design).
"""
from __future__ import annotations

import ast
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PKG = _HERE / 'python' / 'pkg-v12'
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

_SCALAR = ('int', 'float', 'bool', 'str')
_LIST = ('list[int]', 'list[float]')
_MUTATORS = frozenset({
    'append', 'extend', 'insert', 'pop', 'remove', 'clear', 'sort', 'reverse',
    'update', 'add', 'discard', '__setitem__', '__delitem__', 'setdefault',
})
_EXT_SUFFIX = sysconfig.get_config_var('EXT_SUFFIX') or '.so'


def _module_name(stem):
    clean = re.sub(r'[^A-Za-z0-9_]', '_', stem)
    if not clean or clean[0].isdigit():
        clean = '_' + clean
    return '_ail_%s_fast' % clean


def _top_level_functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


# ---- method kernels -----------------------------------------------------------------------------
#
# A plain class method is lifted to a top-level kernel whose `self.<field>` reads and writes are
# ordinary parameters of the field's kind.  The C wrapper below reads those fields from the
# CPython object before the call and writes the changed numeric fields back afterwards, so the
# method body itself needs no CPython object model and runs on the same typed ABI as a top-level
# function.  A method that calls another method (`self.m(...)`) stays in CPython: CPython resolves
# that call dynamically, so a subclass override, an instance attribute or a monkeypatched class
# attribute would change which function runs and a direct kernel call would ignore it.  Everything
# this pass cannot prove stays in CPython with a named reason.

_METHOD_PREFIX = '__ail_hybrid_method_'
_FIELD_PREFIX = '__ail_hybrid_field_'
_METHOD_KINDS = frozenset({'int', 'float', 'bool', 'str', 'list[int]', 'list[float]'})
_METHOD_WRITE_KINDS = frozenset({'int', 'float', 'bool'})

_STR_METHOD_KIND = {
    'upper': 'str', 'lower': 'str', 'casefold': 'str', 'strip': 'str', 'lstrip': 'str',
    'rstrip': 'str', 'capitalize': 'str', 'title': 'str', 'swapcase': 'str',
    'replace': 'str', 'removeprefix': 'str', 'removesuffix': 'str', 'join': 'str',
    'find': 'int', 'rfind': 'int', 'count': 'int',
    'startswith': 'bool', 'endswith': 'bool', 'isdigit': 'bool', 'isalpha': 'bool',
    'isalnum': 'bool', 'isspace': 'bool', 'isupper': 'bool', 'islower': 'bool',
    'istitle': 'bool', 'isdecimal': 'bool', 'isnumeric': 'bool', 'isidentifier': 'bool',
    'isprintable': 'bool', 'isascii': 'bool',
}


def _ann_kind_text(node):
    """The simplest typed kind an annotation spells, or None.  Mirrors the analysis seed."""
    if isinstance(node, ast.Name):
        return node.id if node.id in ('int', 'float', 'str', 'bool') else None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
            and node.value.id == 'list':
        item = node.slice
        if isinstance(item, ast.Name) and item.id in ('int', 'float'):
            return 'list[%s]' % item.id
    return None


def _kind_ast(kind):
    if kind.startswith('list['):
        return ast.Subscript(value=ast.Name(id='list', ctx=ast.Load()),
                             slice=ast.Name(id=kind[5:-1], ctx=ast.Load()), ctx=ast.Load())
    return ast.Name(id=kind, ctx=ast.Load())


def _merge_method_kind(a, b):
    """Field evidence is exact: CPython distinguishes a bool from an int and an int from a
    float, and a write back through the typed ABI can only reproduce one of them.  Disagreement
    therefore stays unresolved instead of being promoted."""
    if a is None or b is None:
        return None
    return a if a == b else None


def _field_expr_kind(expr, param_kinds):
    if isinstance(expr, ast.Constant):
        value = expr.value
        if isinstance(value, bool):
            return 'bool'
        if isinstance(value, int):
            return 'int'
        if isinstance(value, float):
            return 'float'
        if isinstance(value, str):
            return 'str'
        return None
    if isinstance(expr, ast.Name):
        return param_kinds.get(expr.id)
    if isinstance(expr, ast.List):
        kind = None
        for element in expr.elts:
            kind = _merge_method_kind(kind, _field_expr_kind(element, param_kinds)) \
                if kind is not None else _field_expr_kind(element, param_kinds)
            if kind is None:
                return None
        if kind in ('int', 'float', 'str'):
            return 'list[%s]' % kind
        return None
    if isinstance(expr, ast.BinOp):
        left = _field_expr_kind(expr.left, param_kinds)
        right = _field_expr_kind(expr.right, param_kinds)
        if isinstance(expr.op, ast.Add) and left == right == 'str':
            return 'str'
        if left in ('int', 'float', 'bool') and right in ('int', 'float', 'bool'):
            if isinstance(expr.op, ast.Div):
                return 'float'
            return _merge_method_kind(left, right)
        return None
    if isinstance(expr, ast.UnaryOp):
        if isinstance(expr.op, ast.Not):
            return 'bool'
        return _field_expr_kind(expr.operand, param_kinds)
    if isinstance(expr, ast.Compare):
        return 'bool'
    if isinstance(expr, ast.BoolOp):
        # `a or b` evaluates to one of its operands, so the result kind is theirs only when they
        # agree; `x or 0` is an int and `x or True` can be either.
        kinds = [_field_expr_kind(v, param_kinds) for v in expr.values]
        first = kinds[0]
        return first if first is not None and all(k == first for k in kinds) else None
    if isinstance(expr, ast.IfExp):
        return _merge_method_kind(_field_expr_kind(expr.body, param_kinds),
                                  _field_expr_kind(expr.orelse, param_kinds))
    if isinstance(expr, ast.Call):
        func = expr.func
        if isinstance(func, ast.Name):
            if func.id == 'len':
                return 'int'
            if func.id == 'int':
                return 'int'
            if func.id == 'float':
                return 'float'
            if func.id == 'str':
                return 'str'
            if func.id == 'bool':
                return 'bool'
            if func.id == 'abs' and len(expr.args) == 1:
                return _field_expr_kind(expr.args[0], param_kinds)
            return None
        if isinstance(func, ast.Attribute):
            return _STR_METHOD_KIND.get(func.attr)
    return None


_CLASS_REFUSED_NAMES = frozenset({
    '__slots__', '__getattr__', '__getattribute__', '__setattr__', '__delattr__',
    '__dict__', '__weakref__', '__metaclass__',
})


def _plain_class(node):
    """A class this pass is willing to look at: no bases/metaclass/decorators, methods only, and
    no attribute protocol of its own.  `self.<field>` must be an ordinary instance-dict lookup and
    store, or the C wrapper's `PyObject_GetAttrString`/`PyObject_SetAttrString` would observe
    different behaviour than CPython's bytecode."""
    if node.decorator_list or node.bases or node.keywords:
        return False
    for stmt in node.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) \
                and isinstance(stmt.value.value, str):
            continue
        if isinstance(stmt, ast.Pass):
            continue
        if not isinstance(stmt, ast.FunctionDef) or stmt.decorator_list:
            return False
        if stmt.name in _CLASS_REFUSED_NAMES:
            return False
    return True


def _plain_method(fn):
    args = fn.args
    if args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults:
        return False
    if not args.args or args.args[0].arg != 'self':
        return False
    return True


def _class_base_names(node):
    names = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


def _bound_class_names(stmt):
    """Names a statement binds in the class body (its own namespace, not a nested scope)."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {stmt.name}
    if isinstance(stmt, ast.Assign):
        out = set()
        for target in stmt.targets:
            for node in ast.walk(target):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    out.add(node.id)
        return out
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return {stmt.target.id}
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return {(alias.asname or alias.name).split('.')[0] for alias in stmt.names}
    return set()


_ATTR_HAZARDS = frozenset({
    '__getattr__', '__getattribute__', '__setattr__', '__delattr__', '__slots__',
})


def _field_override_subclass(classdef, classes, field_names):
    """The first related class that can change `self.<field>` access, or None.

    The wrapper reads each needed field once and writes each changed field once, while CPython
    re-evaluates every occurrence.  That is only invisible for an ordinary instance-dict field.
    A subclass (or a mixin on its MRO) that binds a field name in its class body -- a `property`,
    a method, a slot, ... -- or defines an attribute protocol hook makes each access observable,
    so the batched wrapper could answer differently.  Refuse the parent's methods by name.
    """
    parent = classdef.name
    descendants = set()
    changed = True
    while changed:
        changed = False
        for name, cdef in classes.items():
            if name == parent or name in descendants:
                continue
            if any(base == parent or base in descendants
                   for base in _class_base_names(cdef)):
                descendants.add(name)
                changed = True
    related = set(descendants)
    for name in descendants:
        stack = list(_class_base_names(classes[name]))
        seen = set()
        while stack:
            base = stack.pop()
            if base in seen or base == parent:
                continue
            seen.add(base)
            related.add(base)
            if base in classes:
                stack.extend(_class_base_names(classes[base]))
    for name in sorted(related):
        for stmt in classes[name].body:
            bound = _bound_class_names(stmt)
            if bound & field_names or bound & _ATTR_HAZARDS:
                return name
    return None


def _class_fields(classdef, init_kinds=None):
    """[(field, kind)] from the class's own __init__, or (None, reason).

    `init_kinds` maps a positional `__init__` argument index (self excluded) to a kind proved from
    the module's own `ClassName(...)` call sites; an annotation always wins because it is the
    stronger source.  The value still crosses the C wrapper's exact-type check, so a wrong guess
    falls back to the original method rather than changing an answer."""
    init = None
    for stmt in classdef.body:
        if isinstance(stmt, ast.FunctionDef) and stmt.name == '__init__':
            init = stmt
            break
    if init is None or not _plain_method(init):
        return None, 'the class has no plain __init__'
    init_kinds = init_kinds or {}
    params = {a.arg: (_ann_kind_text(a.annotation)
                      or init_kinds.get(i))
              for i, a in enumerate(init.args.args[1:])}
    fields, order = {}, []
    for node in _own_nodes(init):
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
            ann_kind = _ann_kind_text(node.annotation)
        elif isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                continue
            target, value = node.targets[0], node.value
            ann_kind = None
        else:
            continue
        if not (isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name) and target.value.id == 'self'):
            continue
        kind = ann_kind or (_field_expr_kind(value, params) if value is not None else None)
        if target.attr in fields:
            merged = _merge_method_kind(fields[target.attr], kind)
            if merged is None:
                return None, 'field %r has more than one kind' % target.attr
            fields[target.attr] = merged
        else:
            fields[target.attr] = kind
            order.append(target.attr)
    if not fields:
        return None, 'the class has no fields'
    return [(name, fields[name]) for name in order], None


def _self_attr(node, selfname):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and node.value.id == selfname:
        return node.attr
    return None


class _SelfUse(ast.NodeVisitor):
    """Reads, writes and `self.method` calls of one method, refusing any other use of self."""

    def __init__(self, selfname):
        self.selfname = selfname
        self.reads, self.writes, self.calls = set(), set(), set()
        self.reason = None

    def fail(self, reason):
        if self.reason is None:
            self.reason = reason

    def visit_FunctionDef(self, node):
        self.fail('a nested function captures this method scope')

    def visit_AsyncFunctionDef(self, node):
        self.fail('a nested function captures this method scope')

    def visit_Lambda(self, node):
        self.fail('a lambda captures this method scope')

    def visit_AugAssign(self, node):
        attr = _self_attr(node.target, self.selfname)
        if attr is not None:
            self.reads.add(attr)
            self.writes.add(attr)
            self.visit(node.value)
            return
        self.generic_visit(node)

    def visit_Attribute(self, node):
        attr = _self_attr(node, self.selfname)
        if attr is not None:
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                self.writes.add(attr)
            else:
                self.reads.add(attr)
            return
        if any(isinstance(n, ast.Name) and n.id == self.selfname
               for n in ast.walk(node.value)):
            self.fail('self is used other than as `self.<field>`')
            return
        self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == self.selfname:
            self.calls.add(func.attr)
            for arg in node.args:
                self.visit(arg)
            for keyword in node.keywords:
                self.visit(keyword.value)
            return
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == self.selfname:
            self.fail('self is used other than as `self.<field>`')


def _collect_self_use(fn):
    use = _SelfUse('self')
    for stmt in fn.body:
        use.visit(stmt)
    return use


class _MethodRefused(Exception):
    pass


class _MethodBody(ast.NodeTransformer):
    """Rewrite `self.x` to a field parameter.

    A `self.m(...)` call is never rewritten: CPython resolves it dynamically, so an override in a
    subclass, an instance attribute or a monkeypatched class attribute would be ignored by a direct
    kernel call.  Such a method is refused before this pass runs; the call check here is a guard.
    """

    def __init__(self, fields):
        self.fields = fields                  # field name -> (kernel index, kind)

    def visit_FunctionDef(self, node):
        raise _MethodRefused('a nested function captures this method scope')

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == 'self':
            if node.attr not in self.fields:
                raise _MethodRefused('unknown field %r' % node.attr)
            index, kind = self.fields[node.attr]
            if isinstance(node.ctx, (ast.Store, ast.Del)) and kind not in _METHOD_WRITE_KINDS:
                raise _MethodRefused('a write to a %s field' % kind)
            if isinstance(node.ctx, ast.Del):
                raise _MethodRefused('delete of a field')
            ctx = ast.Store() if isinstance(node.ctx, ast.Store) else ast.Load()
            return ast.copy_location(
                ast.Name(id=_FIELD_PREFIX + str(index), ctx=ctx), node)
        if any(isinstance(n, ast.Name) and n.id == 'self' for n in ast.walk(node.value)):
            raise _MethodRefused('self is used other than as `self.<field>`')
        return self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == 'self':
            raise _MethodRefused('a call to another method stays in CPython')
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == 'self':
            raise _MethodRefused('self is used other than as `self.<field>`')
        return node


class _ReturnField(ast.NodeTransformer):
    def __init__(self, name):
        self.name = name

    def visit_Return(self, node):
        return ast.copy_location(ast.Return(value=ast.Name(id=self.name, ctx=ast.Load())), node)


def _method_kernel_name(class_name, method_name):
    return _METHOD_PREFIX + class_name + '_' + method_name


def _walk_stmts(nodes):
    """Every node of a statement list, without entering a nested def (which is its own scope)."""
    stack = list(nodes)
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def _infer_call_kinds(tree):
    """Kinds proved at this module's own call sites, for constructor and `self.m(...)` arguments.

    The value is only a *hint*: every lifted kernel argument crosses the C wrapper's exact-type
    check, so a hint that the runtime contradicts falls back to the original Python method.  Only
    literals, annotated parameters and `self.<field>` reads of already-typed fields contribute, so
    nothing is guessed from an unrelated scope.
    """
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    ctor, methods = {}, {}

    def add(table, key, args, names, fields):
        slot = table.setdefault(key, {})
        for i, arg in enumerate(args):
            if isinstance(arg, ast.Starred):
                slot[i] = None
                continue
            kind = _field_expr_kind(arg, names)
            if kind is None and isinstance(arg, ast.Attribute) \
                    and isinstance(arg.value, ast.Name) and arg.value.id == 'self' and fields:
                kind = fields.get(arg.attr)
            if kind is None:
                slot[i] = None
            elif slot.get(i, kind) != kind:
                slot[i] = None
            else:
                slot[i] = kind

    def scan(nodes, names, fields, cls):
        for node in nodes:
            for n in ast.walk(node):
                if not isinstance(n, ast.Call) or n.keywords:
                    continue
                func = n.func
                if isinstance(func, ast.Name) and func.id in classes:
                    add(ctor, func.id, n.args, names, None)
                elif cls is not None and isinstance(func, ast.Attribute) \
                        and isinstance(func.value, ast.Name) and func.value.id == 'self':
                    add(methods, (cls, func.attr), n.args, names, fields)

    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef):
            continue
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = {a.arg: _ann_kind_text(a.annotation) for a in stmt.args.args}
            scan([stmt], names, None, None)
        else:
            scan([stmt], {}, None, None)
    for cname, cdef in classes.items():
        init = next((s for s in cdef.body
                     if isinstance(s, ast.FunctionDef) and s.name == '__init__'), None)
        if init is None or not _plain_method(init):
            continue
        fields, _why = _class_fields(cdef)
        fields = dict(fields or [])
        for stmt in cdef.body:
            if not isinstance(stmt, ast.FunctionDef) or stmt.name == '__init__':
                continue
            names = {a.arg: _ann_kind_text(a.annotation) for a in stmt.args.args}
            scan([stmt], names, fields, cname)
    return ctor, methods


def _write_kinds_ok(body_nodes, field_params, param_kinds):
    """A write back through the C wrapper serialises the field as its declared kind.  A CPython
    assignment can store a different type (`self.n = True` into an int field), so every field
    store must be proved to carry exactly the field's own kind; otherwise the method stays in
    CPython and keeps CPython's object identity."""
    for node in _walk_stmts(body_nodes):
        if isinstance(node, ast.Assign):
            kind = _field_expr_kind(node.value, param_kinds)
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in field_params:
                    if kind != field_params[target.id]:
                        return False
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id in field_params:
                kind = _field_expr_kind(node.value, param_kinds)
                cur = field_params[node.target.id]
                if kind is None or _merge_method_kind(cur, kind) != cur:
                    return False
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in field_params \
                    and node.value is not None:
                if _field_expr_kind(node.value, param_kinds) != field_params[node.target.id]:
                    return False
    return True


def _method_kernels(tree):
    """Plan every plain-class method: its fields, kernels and refusals.  Pure planning only."""
    ctor_kinds, method_kinds = _infer_call_kinds(tree)
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    plan = {}
    for classdef in tree.body:
        if not isinstance(classdef, ast.ClassDef):
            continue
        methods = {}
        if _plain_class(classdef):
            fields, why = _class_fields(classdef, ctor_kinds.get(classdef.name))
            if fields is not None:
                field_kinds = dict(fields)
                hazard = _field_override_subclass(classdef, classes, set(field_kinds))
                if hazard is not None:
                    reason = ('subclass %r can change field access, so a batched wrapper '
                              'would differ' % hazard)
                    for stmt in classdef.body:
                        if isinstance(stmt, ast.FunctionDef) and stmt.name != '__init__':
                            methods[stmt.name] = {'reason': reason}
                    plan[classdef.name] = {'class': classdef, 'fields': fields,
                                           'methods': methods, 'reason': None}
                    continue
                for stmt in classdef.body:
                    if not isinstance(stmt, ast.FunctionDef) or stmt.name == '__init__':
                        continue
                    if not _plain_method(stmt):
                        methods[stmt.name] = {'reason': 'the method has defaults, *args or **kwargs'}
                        continue
                    use = _collect_self_use(stmt)
                    if use.reason:
                        methods[stmt.name] = {'reason': use.reason}
                        continue
                    if use.calls:
                        # `self.m(...)` must keep CPython's dynamic dispatch: a subclass override,
                        # an instance attribute or a monkeypatched class attribute can change which
                        # function runs, and a direct kernel call would ignore all three.
                        methods[stmt.name] = {
                            'reason': 'a call to another method %r stays in CPython'
                                      % sorted(use.calls)[0]}
                        continue
                    unknown = [a for a in use.reads | use.writes if a not in field_kinds]
                    if unknown:
                        methods[stmt.name] = {'reason': 'unknown field %r' % sorted(unknown)[0]}
                        continue
                    unsupported = [a for a in use.reads if field_kinds[a] not in _METHOD_KINDS]
                    if unsupported:
                        methods[stmt.name] = {'reason': 'field %r has no typed kind' % unsupported[0]}
                        continue
                    bad_write = [a for a in use.writes
                                 if field_kinds[a] not in _METHOD_WRITE_KINDS]
                    if bad_write:
                        methods[stmt.name] = {'reason': 'a write to a %s field'
                                                        % field_kinds[bad_write[0]]}
                        continue
                    methods[stmt.name] = {'fn': stmt, 'reads': set(use.reads),
                                          'writes': set(use.writes),
                                          'arg_kinds': method_kinds.get((classdef.name, stmt.name))}
                for name, info in methods.items():
                    if 'reason' in info:
                        continue
                    needed = info['reads'] | info['writes']
                    info['needed'] = [f for f, _k in fields if f in needed]
                for name, info in methods.items():
                    if 'reason' in info:
                        continue
                    try:
                        _make_method_kernels(classdef.name, name, info, field_kinds)
                    except (KeyError, _MethodRefused, IndexError, TypeError):
                        info['reason'] = 'the method body is not a plain field/self-method body'
                plan[classdef.name] = {'class': classdef, 'fields': fields,
                                       'methods': methods, 'reason': None}
            else:
                plan[classdef.name] = {'class': classdef, 'fields': [], 'methods': {},
                                       'reason': why}
        else:
            plan[classdef.name] = {'class': classdef, 'fields': [], 'methods': {},
                                   'reason': 'not a plain class'}
    return plan


def _make_method_kernels(class_name, method_name, info, field_kinds):
    needed = info['needed']
    index_of = {f: i for i, f in enumerate(needed)}
    fields_map = {f: (index_of[f], field_kinds[f]) for f in needed}
    method_fn = info['fn']
    rewriter = _MethodBody(fields_map)
    body = [rewriter.visit(copy.deepcopy(stmt)) for stmt in method_fn.body]
    field_args = [ast.arg(arg=_FIELD_PREFIX + str(index_of[f]),
                          annotation=_kind_ast(field_kinds[f]))
                  for f in needed]
    arg_kinds = info.get('arg_kinds') or {}
    method_args = []
    for i, arg in enumerate(method_fn.args.args[1:]):
        arg = copy.deepcopy(arg)
        if arg.annotation is None and arg_kinds.get(i) is not None:
            arg.annotation = _kind_ast(arg_kinds[i])
        method_args.append(arg)
    param_kinds = {_FIELD_PREFIX + str(index_of[f]): field_kinds[f] for f in needed}
    param_kinds.update({arg.arg: _ann_kind_text(arg.annotation) for arg in method_args})
    if not _write_kinds_ok(body, {_FIELD_PREFIX + str(index_of[f]): field_kinds[f]
                                  for f in info['writes']}, param_kinds):
        raise _MethodRefused('a field store is not proved to carry the field kind')
    base = _method_kernel_name(class_name, method_name)
    result = ast.FunctionDef(
        name=base,
        args=ast.arguments(posonlyargs=[], args=field_args + method_args, vararg=None,
                           kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=body, decorator_list=[], returns=copy.deepcopy(method_fn.returns),
        type_params=[])
    ast.fix_missing_locations(result)
    info['kernel'] = result
    info['kernel_name'] = base
    info['field_kernels'] = {}
    for field in sorted(info['writes']):
        field_body = copy.deepcopy(body)
        field_body = [_ReturnField(_FIELD_PREFIX + str(index_of[field])).visit(stmt)
                      for stmt in field_body]
        field_body.append(ast.Return(value=ast.Name(id=_FIELD_PREFIX + str(index_of[field]),
                                                    ctx=ast.Load())))
        fk = ast.FunctionDef(
            name=base + '__get_' + field,
            args=ast.arguments(posonlyargs=[], args=copy.deepcopy(field_args + method_args),
                               vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None,
                               defaults=[]),
            body=field_body, decorator_list=[], returns=_kind_ast(field_kinds[field]),
            type_params=[])
        ast.fix_missing_locations(fk)
        info['field_kernels'][field] = fk


def _method_kernel_nodes(plan):
    """Every kernel FunctionDef this plan would add to the analysis source."""
    out = []
    for class_plan in plan.values():
        for info in class_plan['methods'].values():
            if 'reason' in info:
                continue
            out.append(info['kernel'])
            out.extend(info['field_kernels'][f] for f in sorted(info['field_kernels']))
    return out


def _own_nodes(fn):
    """Walk one function's body without entering a nested def (that def is its own candidate)."""
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def _constant_value(node):
    """The value of a numeric literal, including its unary sign (`-3`, `+2`)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _constant_value(node.operand)
        if value is not None:
            return -value if isinstance(node.op, ast.USub) else value
    return None


def _nonzero_constant(node):
    """A literal divisor this pass can prove nonzero (`t % 8`, `x // -3`)."""
    value = _constant_value(node)
    return value is not None and value != 0


_SAFE_STR_NOARGS = frozenset({
    'upper', 'lower', 'casefold', 'strip', 'lstrip', 'rstrip', 'capitalize', 'title',
    'swapcase', 'split', 'rsplit', 'splitlines', 'isdigit', 'isalpha', 'isalnum',
    'isspace', 'isupper', 'islower', 'istitle', 'isdecimal', 'isnumeric', 'isidentifier',
    'isprintable', 'isascii',
})
_SAFE_STR_LITERAL_ARGS = frozenset({
    'strip', 'lstrip', 'rstrip', 'split', 'rsplit', 'replace', 'removeprefix',
    'removesuffix', 'find', 'rfind', 'count', 'startswith', 'endswith',
})
_STR_RESULT_NOARGS = frozenset({
    'upper', 'lower', 'casefold', 'strip', 'lstrip', 'rstrip', 'capitalize', 'title',
    'swapcase',
})
_STR_RESULT_ARGS = frozenset({
    'strip', 'lstrip', 'rstrip', 'replace', 'removeprefix', 'removesuffix',
})
_STR_LIST_METHODS = frozenset({'split', 'rsplit', 'splitlines'})


def _str_literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _int_literal(node):
    if isinstance(node, ast.Constant):
        return isinstance(node.value, int) and not isinstance(node.value, bool)
    return (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub))
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int)
            and not isinstance(node.operand.value, bool))


def _safe_str_method_args(method, args):
    """Argument shapes that cannot make a str method raise: only the exact types CPython wants."""
    if method in ('strip', 'lstrip', 'rstrip'):
        return len(args) <= 1 and (not args or _str_literal(args[0])
                                   or (isinstance(args[0], ast.Constant) and args[0].value is None))
    if method in ('split', 'rsplit'):
        if not args:
            return True
        sep = args[0]
        if not ((_str_literal(sep) and sep.value != '')
                or (isinstance(sep, ast.Constant) and sep.value is None)):
            return False
        return len(args) <= 2 and (len(args) < 2 or _int_literal(args[1]))
    if method == 'replace':
        return (1 <= len(args) <= 3 and _str_literal(args[0]) and _str_literal(args[1])
                and (len(args) < 3 or _int_literal(args[2])))
    if method in ('removeprefix', 'removesuffix'):
        return len(args) == 1 and _str_literal(args[0])
    if method in ('find', 'rfind', 'count', 'startswith', 'endswith'):
        return (1 <= len(args) <= 3 and _str_literal(args[0])
                and all(_int_literal(a) for a in args[1:]))
    return False


def _provably_str(node, str_names):
    """A str result proved from a str parameter, a str literal, and the str methods that always
    return str.  CPython does not enforce annotations, so only the body's own evidence counts."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.Name):
        return node.id in str_names
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _provably_str(node.left, str_names) and _provably_str(node.right, str_names)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if not _provably_str(node.func.value, str_names) or node.keywords:
                return False
            if attr == 'join':
                return len(node.args) == 1 and _provably_str_seq(node.args[0], str_names)
            if attr in _STR_RESULT_NOARGS and not node.args:
                return True
            if attr in _STR_RESULT_ARGS and _safe_str_method_args(attr, node.args):
                return True
    return False


def _provably_str_seq(node, str_names):
    """An iterable whose elements are all str, so `join`/`sorted`/`reversed` cannot raise."""
    if _provably_str(node, str_names):
        return True
    if isinstance(node, ast.List):
        return all(_provably_str(e, str_names) for e in node.elts)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == 'reversed' \
                and len(node.args) == 1 and not node.keywords:
            return _provably_str_seq(node.args[0], str_names)
        if isinstance(node.func, ast.Attribute) and node.func.attr in _STR_LIST_METHODS \
                and not node.keywords and _provably_str(node.func.value, str_names):
            return _safe_str_method_args(node.func.attr, node.args)
    return False


def _provably_list(node, list_names):
    if isinstance(node, ast.Name):
        return node.id in list_names
    if isinstance(node, ast.List):
        return True
    return False


def _provably_number(node, num_names, float_names=(), int_names=(), int_result=False):
    """An int/float/bool parameter or literal, or a sign applied to one: `str` of these cannot
    raise.  A unary `-` of an int can overflow on INT64_MIN, so it is safe only when the clone's
    int/bool result routes that through the overflow wrapper; a float negation is always safe.
    (Overflow of a bare int is not an arithmetic result and so is not relevant here.)"""
    if isinstance(node, ast.Name):
        return node.id in num_names
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        if _provably_float(node.operand, float_names):
            return True
        if isinstance(node.op, ast.UAdd):
            return _provably_number(node.operand, num_names, float_names, int_names,
                                    int_result)
        return int_result and _provably_int(node.operand, int_names, int_result)
    return False


def _provably_int(node, int_names, int_result=False, bool_names=(), allow_bool=True):
    """A value `int()` is the identity on: an int/bool parameter or literal (a float is not one;
    `int(<float>)` can raise ValueError/OverflowError, which a clone cannot reproduce here).  A
    unary `-` of an int needs the int/bool result's overflow wrapper, as in `_provably_number`.

    `allow_bool=False` additionally rejects a bool value.  `abs` preserves boolness (and a unary
    `+`/`-` of a bool stays bool in the typed clone), so `abs(<bool>)` returns a bool where CPython
    returns an int; only `int(...)` converts it, so that call resets the flag."""
    if isinstance(node, ast.Name):
        return node.id in int_names and (allow_bool or node.id not in bool_names)
    if isinstance(node, ast.Constant):
        return isinstance(node.value, int) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        if isinstance(node.op, ast.UAdd):
            return _provably_int(node.operand, int_names, int_result, bool_names, allow_bool)
        return int_result and _provably_int(node.operand, int_names, int_result, bool_names,
                                            allow_bool)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ('int', 'abs') and len(node.args) == 1 and not node.keywords:
        if node.func.id == 'int':
            return _provably_int(node.args[0], int_names, int_result, bool_names, True)
        return _provably_int(node.args[0], int_names, int_result, bool_names, False)
    return False


def _provably_float(node, float_names):
    if isinstance(node, ast.Name):
        return node.id in float_names
    if isinstance(node, ast.Constant):
        return isinstance(node.value, float)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _provably_float(node.operand, float_names)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ('int', 'float', 'abs') and len(node.args) == 1 \
            and not node.keywords:
        return _provably_float(node.args[0], float_names)
    return False


def _safe_call(node, str_names, list_names, num_names=(), int_names=(), float_names=(), ret=None,
               bool_names=(), allowed_calls=()):
    """A call this pass can prove cannot raise and has no side effect.  Everything else stays a
    refusal: the hybrid must return CPython's value or fall back, never a partial answer."""
    func = node.func
    if isinstance(func, ast.Name) and func.id in allowed_calls:
        # A read-only method kernel: its own body passed the same gate, and its arguments are
        # visited independently by `_unsafe_body`.
        return True
    if isinstance(func, ast.Attribute):
        receiver = func.value
        if _provably_str(receiver, str_names):
            if not node.keywords:
                if not node.args and func.attr in _SAFE_STR_NOARGS:
                    return True
                if func.attr in _SAFE_STR_LITERAL_ARGS and \
                        _safe_str_method_args(func.attr, node.args):
                    return True
                if func.attr == 'join' and len(node.args) == 1 \
                        and _provably_str_seq(node.args[0], str_names):
                    return True
            return False
        if _provably_list(receiver, list_names) and func.attr == 'copy' \
                and not node.args and not node.keywords:
            return True
        return False
    if not isinstance(func, ast.Name) or node.keywords:
        return False
    args = node.args
    if func.id == 'len' and len(args) == 1:
        return (_provably_str(args[0], str_names) or _provably_list(args[0], list_names)
                or isinstance(args[0], ast.List))
    if func.id == 'reversed' and len(args) == 1:
        return _provably_str_seq(args[0], str_names) or _provably_list(args[0], list_names)
    if func.id == 'abs' and len(args) == 1:
        # float abs is fabs; int abs can overflow only on INT64_MIN, which an int/bool result
        # routes through the clone's overflow wrapper (and so back to CPython).  A str/list
        # result has no such wrapper, so an int abs stays refused there.
        return (_provably_float(args[0], float_names)
                or (ret in ('int', 'bool')
                    and _provably_int(args[0], int_names, True, bool_names, False)))
    if func.id == 'int' and len(args) <= 1:
        # int(<int/bool>) is the identity; int(<float>) can raise ValueError/OverflowError,
        # which this clone cannot reproduce without an overflow wrapper for every result kind.
        # A unary minus of an int is the same overflow question as in `str`.
        return not args or _provably_int(args[0], int_names, ret in ('int', 'bool'))
    if func.id == 'str' and len(args) <= 1:
        # `str(-x)` overflows on INT64_MIN unless the int/bool result's wrapper can fall back.
        return not args or _provably_number(args[0], num_names, float_names, int_names,
                                             ret in ('int', 'bool')) \
            or _provably_str(args[0], str_names)
    return False


def _unsafe_body(fn, params=(), ret=None, allowed_calls=()):
    """Operations whose typed form traps or leaves Python's exception model.  A hybrid call must
    either return CPython's value or fall back, so a body that can raise stays in CPython: a
    subscript (IndexError/KeyError), division or power (ZeroDivisionError, complex results), an
    arbitrary call, and `raise`/`assert`/`try`/`with`/import are all outside this pass.  A division
    by a literal nonzero divisor cannot raise, and a call to a pure str method (or `len`,
    `reversed`) whose receiver and arguments are provably the right type cannot raise either, so
    both stay eligible.  This is deliberately conservative; a missed speed-up is safe."""
    str_names = {p for p, kind in params if kind == 'str'}
    list_names = {p for p, kind in params if kind in _LIST}
    num_names = {p for p, kind in params if kind in ('int', 'float', 'bool')}
    int_names = {p for p, kind in params if kind in ('int', 'bool')}
    bool_names = {p for p, kind in params if kind == 'bool'}
    float_names = {p for p, kind in params if kind == 'float'}
    for node in _own_nodes(fn):
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                return 'slice indexing can raise'
            # A non-slice index is allowed: the clone's own IndexError/KeyError stop is
            # turned into a per-call fallback (see _trap_patch), so the Python wrapper
            # re-runs the original function and CPython's exception is the one observed.
            continue
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
            if (isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod))
                    and _nonzero_constant(node.right)):
                continue
            return 'division or power can raise'
        if isinstance(node, ast.Call) and not _safe_call(node, str_names, list_names, num_names,
                                                          int_names, float_names, ret, bool_names,
                                                          allowed_calls):
            return 'a call can raise or have side effects'
        if isinstance(node, (ast.Raise, ast.Assert)):
            return 'the function can raise'
        if isinstance(node, (ast.Try, ast.With, ast.Import, ast.ImportFrom)):
            return 'try/with/import is not safe to clone'
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return 'a global assignment is not safe to clone'
        if isinstance(node, ast.Delete):
            return 'delete is not safe to clone'
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            return 'attribute assignment is not safe to clone'
        if isinstance(node, (ast.Await, ast.Yield, ast.YieldFrom)):
            return 'coroutine/generator code stays in CPython'
    return None


def _list_param_mutated(fn, list_params, allowed_calls=()):
    """A list argument is copied into the typed call, so a function that mutates it must stay in
    CPython (mutation would otherwise not be visible to the caller).  This also refuses passing a
    list parameter on to another user function, which may mutate it one step away."""
    if not list_params:
        return False
    # A local assigned straight from a list parameter aliases it in CPython, so mutating the
    # local is mutating the caller's list.  Follow that simple assignment closure before the
    # mutation scan; the typed clone copies the parameter into a C buffer, so such a write would
    # not be visible to the caller.
    aliases = set(list_params)
    nodes = list(_own_nodes(fn))
    changed = True
    while changed:
        changed = False
        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = getattr(node, 'value', None)
                if isinstance(value, ast.Name) and value.id in aliases:
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id not in aliases:
                            aliases.add(target.id)
                            changed = True
    for node in nodes:
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in aliases and node.func.attr in _MUTATORS):
            return True
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id in aliases
                and isinstance(node.ctx, (ast.Store, ast.Del))):
            return True
        if isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id in aliases:
                return True
            if (isinstance(node.target, ast.Subscript) and isinstance(node.target.value, ast.Name)
                    and node.target.value.id in aliases):
                return True
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return True
    # Passing a list to an arbitrary call may let the callee mutate it.  These builtins only read
    # the sequence, so they do not make the caller's copy unsafe.
    nonmutating = frozenset({'len', 'reversed', 'sorted', 'min', 'max', 'sum', 'any', 'all'})
    for node in nodes:
        if isinstance(node, ast.Call) and not (
                isinstance(node.func, ast.Name)
                and (node.func.id in allowed_calls or node.func.id in nonmutating)):
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(arg, ast.Name) and arg.id in aliases:
                    return True
    return False


def _analysis(src):
    """Build the program once through the real CLI and capture its mixed-mode units.

    A direct `pyc.build` call sees the raw Python source; the CLI first runs the Python-surface
    translation, merges local imports and applies the prelude, and that is the source the mixed
    mode analyses.  A subprocess with a temporary `sitecustomize.py` therefore patches the same
    `pyboxed2` and `pymix` objects the CLI uses, lets the CLI do a normal `--syntax python
    --exact-int` build, and writes the captured units to a JSON file.  The exact-int build is
    deliberate: the hybrid promises CPython's answers, so an int literal beyond int64 must not be
    truncated.  If the exact build is refused, a direct `pyboxed2.build` on the same temporary
    source is tried; if that also emits nothing, the hybrid runs as CPython.

    Details loosened only in that subprocess: the entry prototype regex requires a word boundary
    (`ail_unwind_<name>` must not match), the documented str ABI's `uint8_t *_out` result
    parameter is accepted by the existing validator (which writes through `int32_t *`), and
    parameter annotations seed `pymix`'s kinds.  The selection pass below still requires the body
    to have no operation that can trap.
    """
    import tempfile
    fd, name = tempfile.mkstemp(prefix='ail-hybrid-src-', suffix='.py')
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(src)
    source_path = Path(name)
    remove_source = True
    run_dir = Path(tempfile.mkdtemp(prefix='ail-cpython-analysis-'))
    capture_path = run_dir / 'capture.json'
    cli = _HERE / 'ail_chatgpt.py'
    site = run_dir / 'sitecustomize.py'
    site.write_text(r"""
import ast, json, os, re, sys
sys.path.insert(0, %r)
try:
    import pyboxed2, pyfunc, pymix
except Exception:
    raise SystemExit(0)
# The CLI's Python-surface pass marks every annotated return with a `__ail_checked_*__` contract
# (dunders.py), which `to_c` treats as a request for a checked outer contract and refuses for a
# str entry.  Mixed mode never asked for that contract; the body's own proof is the gate and the
# Python wrapper checks the value coming back, so drop only the return marker here.
_old_to_c = pyfunc.to_c
def _to_c(source, *args, **kwargs):
    source = re.sub(r'\s*->\s*__ail_checked_[A-Za-z0-9_]+__', '', source)
    return _old_to_c(source, *args, **kwargs)
pyfunc.to_c = _to_c
# CPython does not enforce annotations, but they are useful hints: the boundary still checks every
# value (a non-int for `x: int` falls back before the native call), and the existing emitter is
# asked to compile the function as usual.  Seeding only the parameter kinds lets a helper such as
# `def byte_length(word: str) -> int` reach to_c, whose own acceptance test remains the gate.
_old_fn_init = pymix._FnFacts.__init__
def _ann_kind(node):
    if isinstance(node, ast.Name):
        return {'int': pymix.INT, 'float': pymix.FLOAT, 'str': pymix.STR,
                'bool': pymix.BOOL, '__ail_checked_int__': pymix.INT,
                '__ail_checked_float__': pymix.FLOAT, '__ail_checked_str__': pymix.STR,
                '__ail_checked_bool__': pymix.BOOL}.get(node.id)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'list':
        item = node.slice
        if isinstance(item, ast.Name) and item.id == 'int':
            return pymix.LIST_INT
        if isinstance(item, ast.Name) and item.id == 'float':
            return pymix.LIST_FLOAT
    return None
def _fn_init(self, node):
    _old_fn_init(self, node)
    for arg in node.args.args:
        kind = _ann_kind(arg.annotation)
        if kind is not None:
            self.params[arg.arg] = kind
pymix._FnFacts.__init__ = _fn_init
# A local dict/list literal has a resolvable element kind even though pymix's base vocabulary
# stops at one container level.  Keep this inference in the hybrid's own analysis process so the
# default (non-hybrid) build path is byte-for-byte unchanged.
_old_expr_kind = pymix._expr_kind
_DICT_PREFIX = '__ail_hybrid_dict__'
def _hybrid_expr_kind(e, facts, rets):
    if isinstance(e, ast.Dict):
        vk = None
        for v in e.values:
            k = _hybrid_expr_kind(v, facts, rets)
            if k is None:
                return None
            vk = k if vk is None else pymix._merge(vk, k)
            if vk is None:
                return None
        return None if vk is None else _DICT_PREFIX + vk
    if isinstance(e, ast.List):
        ek = None
        for el in e.elts:
            k = _hybrid_expr_kind(el, facts, rets)
            if k is None:
                return None
            ek = k if ek is None else pymix._merge(ek, k)
            if ek is None:
                return None
        if ek is None:
            return None
        if ek in (pymix.INT, pymix.FLOAT, pymix.STR):
            return pymix.LIST_OF.get(ek)
        if ek.startswith('list[') or ek.startswith(_DICT_PREFIX):
            return 'list[' + ek + ']'
        return None
    if isinstance(e, ast.Subscript) and not isinstance(e.slice, ast.Slice):
        base = _hybrid_expr_kind(e.value, facts, rets)
        if isinstance(base, str):
            if base.startswith(_DICT_PREFIX):
                return base[len(_DICT_PREFIX):]
            if base.startswith('list[') and base.endswith(']'):
                inner = base[5:-1]
                if inner.startswith(_DICT_PREFIX):
                    inner = inner[len(_DICT_PREFIX):]
                return inner
    if isinstance(e, ast.BoolOp):
        # `a and b` / `a or b` evaluates to one of its operands, so the result kind is known only
        # when every operand has the same scalar kind.  `x or 0` is an int, `x or True` may be
        # either, so a mixed kind is not guessed (pymix's `ast.Compare` rule stays unchanged).
        kinds = [_hybrid_expr_kind(v, facts, rets) for v in e.values]
        first = kinds[0]
        if first in (pymix.INT, pymix.FLOAT, pymix.BOOL, pymix.STR) \
                and all(k == first for k in kinds):
            return first
        return None
    return _old_expr_kind(e, facts, rets)
pymix._expr_kind = _hybrid_expr_kind
# A subscript's IndexError/KeyError is now reproduced by the wrapper re-running the original
# Python function, so it no longer needs pymix's exception-escape rejection in the hybrid.
_old_raise_site = pymix._raise_site_exc
def _raise_site_exc(node):
    if isinstance(node, ast.Subscript):
        return None
    return _old_raise_site(node)
pymix._raise_site_exc = _raise_site_exc
_old_extract = pyboxed2._mix_extract_signature
_old_validate = pyboxed2._mix_validate_signature
_old_build = pyboxed2.build
_old_analyze = pymix.analyze
_last = {}
def _extract(csrc, mangled):
    m = re.search(r'^([A-Za-z_][\w ]*\*?\s*\b' + re.escape(mangled) + r'\s*\([^\n{;]*\))\s*\{', csrc, re.MULTILINE)
    return m.group(1) if m else None
def _validate(sig_text, mangled, params, ret):
    return _old_validate(sig_text.replace('uint8_t *_out', 'int32_t *_out'), mangled, params, ret)
def _facts():
    facts = {}
    analysis = _last.get('analysis')
    if analysis is None:
        return facts
    try:
        irs = analysis.function_ir
    except Exception:
        return facts
    for name, ir in irs.items():
        try:
            sig = ir.signature()
            facts[str(name)] = {'params': [[str(p), str(k)] for p, k in sig['params'].items()],
                                'ret': str(sig['ret']), 'is_bool_ret': bool(sig.get('is_bool_ret'))}
        except Exception:
            pass
    return facts
def _pymix_rejected():
    analysis = _last.get('analysis')
    if analysis is None:
        return {}
    try:
        return {str(name): [str(part) for part in why]
                for name, why in (analysis.rejected or {}).items()}
    except Exception:
        return {}
def _dump(report):
    try:
        data = {'mix_units': [list(u) for u in (report.get('mix_units') or [])],
                'typed_inline': list(report.get('typed_inline') or []),
                'facts': _facts(), 'pymix_rejected': _pymix_rejected(),
                'note': str(report.get('note') or '')}
        with open(os.environ['AIL_HYBRID_CAPTURE'], 'w', encoding='utf-8') as handle:
            json.dump(data, handle)
    except Exception:
        pass
def _build(source, report, *args, **kwargs):
    # The mixed-mode ABI is int64 with an overflow -> Python fallback; exact-int lowering makes
    # `to_c` spell parameters as `ail_tint`, which that ABI (and the boxed caller) cannot call.
    # The general build still runs with the CLI's exact setting; only the unit generation below
    # is the int64 ABI. Any value that does not fit falls back to the original Python function.
    saved = os.environ.pop('AIL_EXACT_INT', None)
    try:
        result = _old_build(source, report, *args, **kwargs)
    finally:
        if saved is not None:
            os.environ['AIL_EXACT_INT'] = saved
    _dump(report)
    return result
def _analyze(source, *args, **kwargs):
    result = _old_analyze(source, *args, **kwargs)
    _last['analysis'] = result
    return result
pyboxed2._mix_extract_signature = _extract
pyboxed2._mix_validate_signature = _validate
pyboxed2.build = _build
pymix.analyze = _analyze
""" % str(_PKG), encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=str(run_dir) + os.pathsep + os.environ.get('PYTHONPATH', ''),
               AIL_HYBRID_CAPTURE=str(capture_path), AIL_NO_CACHE='1', AIL_CACHE=str(run_dir / 'cache'),
               AIL_EXACT_INT='1', AIL_SURFACE='python', AIL_GENERAL='v2')
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_NO_MIX', None)
    try:
        proc = subprocess.run([sys.executable, '-B', str(cli), 'compile', str(source_path),
                               '--syntax', 'python', '--exact-int', '-o', str(run_dir / 'analysis-only')],
                              env=env, capture_output=True, text=True, timeout=900)
        if proc.returncode != 0 or not capture_path.exists():
            # The CLI may refuse a program the raw mixed-mode emitter can still slice (a module
            # loop over a tuple, an unsupported import used only by `main`, ...).  A direct
            # pyboxed2 build analyses the original source and can still wire the independent
            # helpers; if that also fails, CPython fallback is the answer.
            capture_path.unlink(missing_ok=True)   # never reuse a partial capture from a failed CLI
            runner = run_dir / 'direct.py'
            runner.write_text(
                'import os, pyboxed2\n'
                'pyboxed2.build(open(os.environ["AIL_HYBRID_SRC"], encoding="utf-8").read(), {}, allow_mix=True)\n',
                encoding='utf-8')
            direct_env = dict(env, AIL_HYBRID_SRC=str(source_path))
            try:
                subprocess.run([sys.executable, '-B', str(runner)], env=direct_env,
                               capture_output=True, text=True, timeout=900)
            except Exception:
                pass
        if not capture_path.exists():
            note = [line for line in (proc.stderr or proc.stdout or '').strip().splitlines() if line.strip()]
            text = note[-1] if note else 'the analysis build was refused'
            return {'mix_units': [], 'typed_inline': [], 'note': text[:600]}, {}
        data = json.loads(capture_path.read_text(encoding='utf-8'))
    except Exception as error:
        return {'mix_units': [], 'typed_inline': [], 'note': ('analysis failed: ' + str(error))[:600]}, {}
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
        if remove_source:
            source_path.unlink(missing_ok=True)
    facts = data.get('facts') or {}
    report = {'mix_units': data.get('mix_units') or [], 'typed_inline': data.get('typed_inline') or [],
              'pymix_rejected': data.get('pymix_rejected') or {},
              'note': data.get('note') or ''}
    return report, facts

def _select(src, tree, report, facts):
    """The units worth wrapping, with the safety filters the design names."""
    import bigcap
    import pymix
    import pyboxed2
    import unified

    funcs = _top_level_functions(tree)
    allowed_calls = {name for name in funcs if name.startswith(_METHOD_PREFIX)}
    big_hard = bigcap.marked(tree, local=False)
    big_local = bigcap.marked(tree)
    id_reach, id_any = pyboxed2._mix_identity_unsafe(tree)
    chosen = {}
    rejected = {}
    for mangled, pyname, csrc in report.get('mix_units') or []:
        if pyname not in funcs:
            continue
        info = facts.get(pyname)
        if info is None:
            continue
        params = [(p, k) for p, k in info.get('params') or []]
        ret = info.get('ret')
        if ret not in _SCALAR:
            rejected[pyname] = 'result kind %s stays in CPython' % ret
            continue
        if pyname in big_hard:
            rejected[pyname] = 'needs an int beyond int64'
            continue
        if pyname in big_local and ret not in ('int', 'bool'):
            rejected[pyname] = 'may overflow but does not return an int'
            continue
        if id_any and (pyname in id_reach or any(k == 'float' for _, k in params) or ret == 'float'):
            rejected[pyname] = 'the program compares numbers with `is`'
            continue
        bad = [k for _, k in params if k not in _SCALAR and k not in _LIST]
        if bad:
            rejected[pyname] = 'parameter kind %s stays in CPython' % bad[0]
            continue
        unsafe = _unsafe_body(funcs[pyname], params, ret, allowed_calls)
        if unsafe:
            rejected[pyname] = unsafe
            continue
        list_params = {p for p, k in params if k in _LIST}
        if _list_param_mutated(funcs[pyname], list_params, allowed_calls):
            rejected[pyname] = 'the list parameter is mutated'
            continue
        chosen[pyname] = {
            'name': pyname, 'mangled': mangled, 'params': params,
            'ret': ret, 'is_bool_ret': bool(info.get('is_bool_ret')),
            'indexes': any(isinstance(n, ast.Subscript) and not isinstance(n.slice, ast.Slice)
                           for n in _own_nodes(funcs[pyname])),
        }
    # wedge1: a function refused before it reaches _select (pymix or the emitter) used to leave
    # no trace, so most refusals were silent.  Name every remaining top-level function too.
    pymix_rejected = report.get('pymix_rejected') or {}
    for pyname in sorted(funcs):
        if pyname in chosen or pyname in rejected:
            continue
        info = facts.get(pyname)
        why = pymix_rejected.get(pyname)
        if info is None:
            if why:
                detail = ': %s' % why[1] if len(why) > 1 and why[1] else ''
                rejected[pyname] = '%s%s stays in CPython' % (why[0], detail)
            else:
                rejected[pyname] = 'not a typed candidate, stays in CPython'
        else:
            rejected[pyname] = ('the typed clone is not wired to the hybrid ABI, stays in CPython')
    return chosen, rejected


_TRAP_DIES = re.compile(
    r'ail_die\("(?:list index out of range|list assignment index out of range|'
    r'pop index out of range|pop from empty list|key error|string index out of range|'
    r'bytes index out of range|grid row index out of range|grid column index out of range)"\)'
    # list-of-objects (nested lists, struct lists) and str/list element helpers report an index
    # trap through the named-exception path instead of `ail_die`.
    r'|ail_raise_named\(AIL_EXC_INDEX\)')


def _trap_patch(csrc, mangled):
    """Turn a clone's index/key runtime stops into a per-call fallback.

    The mixed-mode overflow mechanism already has a `setjmp` landing pad for an int result; this
    adds an independent one (its own flag and jump buffer) for every result kind, so an
    out-of-range list index or a missing dict key abandons the clone and the Python wrapper runs
    the original function.  CPython then supplies the exact IndexError/KeyError, message and
    caller-visible `try/except` behaviour.  Only the unit's own text is changed; no global build
    path is touched.  Returns the patched source, or the original when no prototype is found.
    """
    marker = '#include <stdint.h>\n'
    if marker not in csrc:
        return csrc
    base = mangled + '__hybrid'
    flag, jmp = base + '_trap', base + '_jmp'
    save, savep, hit, call = base + '_save', base + '_savep', base + '_hit', base + '_call'
    match = re.search(r'^([A-Za-z_][\w ]*\*?\s*\b' + re.escape(mangled) +
                      r'\s*\([^\n{;]*\))\s*\{', csrc, re.MULTILINE)
    if match is None:
        return csrc
    proto = match.group(1)
    name_at = re.search(r'\b' + re.escape(mangled) + r'\s*\(', proto).start()
    rtype = re.sub(r'^(?:(?:static|inline|extern)\s+)+', '', proto[:name_at].strip())
    inside = proto[proto.index('(') + 1:proto.rindex(')')]
    args = []
    for arg in inside.split(','):
        arg = arg.strip()
        if arg:
            args.append(re.split(r'[\s*]+', arg)[-1])

    state = {}
    for name in ('ail_depth', 'ail_cleanup_top', 'ail_exc_top'):
        state[name] = bool(re.search(r'^AIL_LINK_STATE\([^;\n]*\b' + name + r'\b', csrc, re.M))
    fields, inits, restores = [], [], []
    if state['ail_depth']:
        fields.append('int64_t depth;')
        inits.append('ail_depth')
        restores.append('        ail_depth = s->depth;')
    if state['ail_cleanup_top']:
        fields.append('ail_cleanup_frame *cleanup;')
        inits.append('ail_cleanup_top')
        restores.extend((
            '        while (ail_cleanup_top && ail_cleanup_top != s->cleanup) {',
            '            ail_cleanup_frame *f = ail_cleanup_top;',
            '            ail_cleanup_top = f->previous;',
            '            f->release(f->resources);',
            '        }',
            '        ail_cleanup_top = s->cleanup;'))
    if state['ail_exc_top']:
        fields.append('int exc_top;')
        inits.append('ail_exc_top')
        restores.append('        ail_exc_top = s->exc_top;')

    decl = ('\n#include <setjmp.h>\n'
            '__thread int %s = 0;\n'
            'static __thread jmp_buf %s;\n'
            'static inline void %s(void);\n' % (flag, jmp, hit))
    if fields:
        helper = ('\ntypedef struct { %s } %s;\n'
                  'static __thread %s *%s;\n'
                  'static inline void %s(void) {\n'
                  '    %s *s = %s;\n'
                  '    if (s) {\n'
                  '%s\n'
                  '    }\n'
                  '    %s = 1;\n'
                  '    longjmp(%s, 1);\n'
                  '}\n' % (' '.join(fields), save, save, savep, hit, save, savep,
                            '\n'.join(restores), flag, jmp))
    else:
        helper = ('\nstatic inline void %s(void) { %s = 1; longjmp(%s, 1); }\n'
                  % (hit, flag, jmp))
    body = [proto.replace(mangled, call, 1) + ' {\n', '    %s = 0;\n' % flag]
    if fields:
        body.extend((
            '    %s saved = {%s};\n' % (save, ', '.join(inits)),
            '    %s *previous = %s;\n' % (save, savep),
            '    %s = &saved;\n' % savep,
            '    if (setjmp(%s) != 0) { %s = previous; return 0; }\n' % (jmp, savep)))
    else:
        body.append('    if (setjmp(%s) != 0) return 0;\n' % jmp)
    body.append('    %s result = %s(%s);\n' % (rtype, mangled, ', '.join(args)))
    if fields:
        body.append('    %s = previous;\n' % savep)
    body.extend(('    return result;\n', '}\n'))
    csrc = _TRAP_DIES.sub(hit + '()', csrc)
    csrc = csrc.replace(marker, marker + decl, 1)
    return csrc + helper + ''.join(body)


def _c_proto(item, symbol=None):
    args = []
    for p, kind in item['params']:
        cn = 'v_' + p
        if kind in ('int', 'bool'):
            args.append('int64_t ' + cn)
        elif kind == 'float':
            args.append('double ' + cn)
        elif kind == 'str':
            args.append('ail_str ' + cn)
        elif kind == 'list[int]':
            args.extend(['const int64_t *' + cn, 'int64_t ' + cn + '_len'])
        elif kind == 'list[float]':
            args.extend(['const double *' + cn, 'int64_t ' + cn + '_len'])
    if item['ret'] == 'str':
        args.extend(['uint8_t *_out', 'int64_t _cap'])
    rtype = 'double' if item['ret'] == 'float' else 'int64_t'
    return '%s %s(%s)' % (rtype, symbol or item['mangled'], ', '.join(args))


def _method_wrapper_lines(item):
    """The C wrapper for one lifted method: read fields from the CPython object, call the result
    kernel, call each written field's kernel, write the new values back, and return the result."""
    name = item['name']
    params = item['params']
    ret = item['ret']
    meta = item['method']
    fields = meta['fields']              # [(index, field, kind)]
    nfields = len(fields)
    method_args = len(params) - nfields
    callee = item['mangled'] + '__hybrid_call' if item.get('indexes') else item['mangled']
    out = ['static PyObject *ail_w_%s(PyObject *module, PyObject *args) {' % name,
           '    PyObject *o[%d];' % max(1, method_args),
           '    PyObject *obj;',
           '    /* METH_VARARGS passes the module as `self`; the Python-level instance is the first'
           ' tuple item (the generated closure passes the bound self positionally). */',
           '    if (PyTuple_GET_SIZE(args) != %d) return ail_hybrid_fallback();' % (method_args + 1),
           '    obj = PyTuple_GET_ITEM(args, 0);']
    if item.get('indexes'):
        out.append('    extern __thread int %s__hybrid_trap;' % item['mangled'])
    bufs = []
    field_objs = []
    for i, (_index, field, kind) in enumerate(fields):
        field_objs.append('fo%d' % i)
        out.append('    PyObject *fo%d = NULL;' % i)
        if kind == 'list[int]':
            out.append('    int64_t *b%d = NULL;' % i)
            bufs.append('b%d' % i)
        elif kind == 'list[float]':
            out.append('    double *b%d = NULL;' % i)
            bufs.append('b%d' % i)
    for j in range(method_args):
        i = nfields + j
        kind = params[i][1]
        if kind == 'list[int]':
            out.append('    int64_t *b%d = NULL;' % i)
            bufs.append('b%d' % i)
        elif kind == 'list[float]':
            out.append('    double *b%d = NULL;' % i)
            bufs.append('b%d' % i)
    fail = 'goto fallback'
    call = []
    for i, (_index, field, kind) in enumerate(fields):
        out.append('    fo%d = PyObject_GetAttrString(obj, %s);' % (i, json.dumps(field)))
        out.append('    if (!fo%d) { PyErr_Clear(); %s; }' % (i, fail))
        src = 'fo%d' % i
        if kind in ('int', 'bool'):
            if kind == 'bool':
                out.append('    if (!PyBool_Check(%s)) %s;' % (src, fail))
                out.append('    int64_t a%d = PyObject_IsTrue(%s) ? 1 : 0;' % (i, src))
            else:
                out.append('    if (!PyLong_CheckExact(%s)) %s;' % (src, fail))
                out.append('    int ovf%d = 0; long long a%d = PyLong_AsLongLongAndOverflow(%s, &ovf%d);'
                           % (i, i, src, i))
                out.append('    if (ovf%d) %s;' % (i, fail))
                out.append('    if (a%d == -1 && PyErr_Occurred()) { PyErr_Clear(); %s; }' % (i, fail))
                out.append('    a%d = (int64_t)a%d;' % (i, i))
        elif kind == 'float':
            out.append('    if (!PyFloat_CheckExact(%s)) %s;' % (src, fail))
            out.append('    double a%d = PyFloat_AsDouble(%s);' % (i, src))
            out.append('    if (a%d == -1.0 && PyErr_Occurred()) { PyErr_Clear(); %s; }' % (i, fail))
        elif kind == 'str':
            out.append('    if (!PyUnicode_CheckExact(%s)) %s;' % (src, fail))
            out.append('    Py_ssize_t n%d = 0; const char *p%d = PyUnicode_AsUTF8AndSize(%s, &n%d);'
                       % (i, i, src, i))
            out.append('    if (!p%d) { PyErr_Clear(); %s; }' % (i, fail))
            out.append('    ail_str a%d; a%d.p = (const uint8_t *)p%d; a%d.n = (int64_t)n%d; a%d.bytes = (PyUnicode_IS_ASCII(%s) ? 1 : 0);'
                       % (i, i, i, i, i, i, src))
        elif kind == 'list[int]':
            out.append('    if (!PyList_CheckExact(%s)) %s;' % (src, fail))
            out.append('    Py_ssize_t n%d = PyList_GET_SIZE(%s);' % (i, src))
            out.append('    b%d = n%d ? (int64_t *)PyMem_Malloc((size_t)n%d * sizeof(int64_t)) : NULL;'
                       % (i, i, i))
            out.append('    if (n%d && !b%d) %s;' % (i, i, fail))
            out.append('    for (Py_ssize_t k%d = 0; k%d < n%d; k%d++) {' % (i, i, i, i))
            out.append('        PyObject *e%d = PyList_GET_ITEM(%s, k%d);' % (i, src, i))
            out.append('        if (!PyLong_CheckExact(e%d)) %s;' % (i, fail))
            out.append('        int ovf%d = 0; long long v%d = PyLong_AsLongLongAndOverflow(e%d, &ovf%d);'
                       % (i, i, i, i))
            out.append('        if (ovf%d) %s;' % (i, fail))
            out.append('        if (v%d == -1 && PyErr_Occurred()) { PyErr_Clear(); %s; }' % (i, fail))
            out.append('        b%d[k%d] = (int64_t)v%d;' % (i, i, i))
            out.append('    }')
            call.append('b%d' % i)
            call.append('(int64_t)n%d' % i)
            continue
        elif kind == 'list[float]':
            out.append('    if (!PyList_CheckExact(%s)) %s;' % (src, fail))
            out.append('    Py_ssize_t n%d = PyList_GET_SIZE(%s);' % (i, src))
            out.append('    b%d = n%d ? (double *)PyMem_Malloc((size_t)n%d * sizeof(double)) : NULL;'
                       % (i, i, i))
            out.append('    if (n%d && !b%d) %s;' % (i, i, fail))
            out.append('    for (Py_ssize_t k%d = 0; k%d < n%d; k%d++) {' % (i, i, i, i))
            out.append('        PyObject *e%d = PyList_GET_ITEM(%s, k%d);' % (i, src, i))
            out.append('        if (!PyFloat_CheckExact(e%d)) %s;' % (i, fail))
            out.append('        double v%d = PyFloat_AsDouble(e%d);' % (i, i))
            out.append('        if (v%d == -1.0 && PyErr_Occurred()) { PyErr_Clear(); %s; }' % (i, fail))
            out.append('        b%d[k%d] = v%d;' % (i, i, i))
            out.append('    }')
            call.append('b%d' % i)
            call.append('(int64_t)n%d' % i)
            continue
        call.append('a%d' % i)
    for j in range(method_args):
        i = nfields + j
        kind = params[i][1]
        out.append('    o[%d] = PyTuple_GET_ITEM(args, %d);' % (j, j + 1))
        src = 'o[%d]' % j
        if kind in ('int', 'bool'):
            if kind == 'bool':
                out.append('    if (!PyBool_Check(%s)) %s;' % (src, fail))
                out.append('    int64_t a%d = PyObject_IsTrue(%s) ? 1 : 0;' % (i, src))
            else:
                out.append('    if (!PyLong_CheckExact(%s)) %s;' % (src, fail))
                out.append('    int ovf%d = 0; long long a%d = PyLong_AsLongLongAndOverflow(%s, &ovf%d);'
                           % (i, i, src, i))
                out.append('    if (ovf%d) %s;' % (i, fail))
                out.append('    if (a%d == -1 && PyErr_Occurred()) { PyErr_Clear(); %s; }' % (i, fail))
                out.append('    a%d = (int64_t)a%d;' % (i, i))
        elif kind == 'float':
            out.append('    if (!PyFloat_CheckExact(%s)) %s;' % (src, fail))
            out.append('    double a%d = PyFloat_AsDouble(%s);' % (i, src))
            out.append('    if (a%d == -1.0 && PyErr_Occurred()) { PyErr_Clear(); %s; }' % (i, fail))
        elif kind == 'str':
            out.append('    if (!PyUnicode_CheckExact(%s)) %s;' % (src, fail))
            out.append('    Py_ssize_t n%d = 0; const char *p%d = PyUnicode_AsUTF8AndSize(%s, &n%d);'
                       % (i, i, src, i))
            out.append('    if (!p%d) { PyErr_Clear(); %s; }' % (i, fail))
            out.append('    ail_str a%d; a%d.p = (const uint8_t *)p%d; a%d.n = (int64_t)n%d; a%d.bytes = (PyUnicode_IS_ASCII(%s) ? 1 : 0);'
                       % (i, i, i, i, i, i, src))
        call.append('a%d' % i)
    cargs = ', '.join(call)
    out.append('    PyObject *res = NULL;')
    # Field write kernels run on the ORIGINAL field values (a method read-only callee cannot
    # change them, and each kernel is pure in its arguments).
    updates = []
    for w in meta['writes']:
        i = w['index']
        wm = w['mangled']
        wcallee = wm + '__hybrid_call' if w.get('indexes') else wm
        if w.get('indexes'):
            out.append('    extern __thread int %s__hybrid_trap;' % wm)
        if w['kind'] == 'float':
            out.append('    double u%d = %s(%s);' % (i, wcallee, cargs))
        else:
            out.append('    extern __thread int %s__mix_overflow;' % wm)
            out.append('    %s__mix_overflow = 0;' % wm)
            out.append('    int64_t u%d = %s(%s);' % (i, wcallee, cargs))
        if w.get('indexes'):
            out.append('    if (%s__hybrid_trap) %s;' % (wm, fail))
        if w['kind'] != 'float':
            out.append('    if (%s__mix_overflow) %s;' % (wm, fail))
        updates.append((i, w))
    if ret == 'str':
        out.append('    int64_t need;')
        out.append('    need = %s(%s%sNULL, 0);' % (callee, cargs, ', ' if cargs else ''))
        if item.get('indexes'):
            out.append('    if (%s__hybrid_trap) %s;' % (item['mangled'], fail))
        out.append('    if (need < 0) %s;' % fail)
        out.append('    uint8_t *sb = (uint8_t *)PyMem_Malloc((size_t)(need > 0 ? need : 1));')
        out.append('    if (!sb) %s;' % fail)
        out.append('    if (need > 0) %s(%s%s(void *)sb, need);'
                   % (callee, cargs, ', ' if cargs else ''))
        if item.get('indexes'):
            out.append('    if (%s__hybrid_trap) { PyMem_Free(sb); %s; }' % (item['mangled'], fail))
        out.append('    res = PyUnicode_DecodeUTF8((const char *)sb, (Py_ssize_t)need, NULL);')
        out.append('    PyMem_Free(sb);')
        out.append('    if (!res) { PyErr_Clear(); %s; }' % fail)
    elif ret == 'float':
        out.append('    double r = %s(%s);' % (callee, cargs))
        if item.get('indexes'):
            out.append('    if (%s__hybrid_trap) %s;' % (item['mangled'], fail))
        out.append('    res = PyFloat_FromDouble(r);')
        out.append('    if (!res) %s;' % fail)
    else:
        out.append('    extern __thread int %s__mix_overflow;' % item['mangled'])
        out.append('    %s__mix_overflow = 0;' % item['mangled'])
        out.append('    int64_t r = %s(%s);' % (callee, cargs))
        if item.get('indexes'):
            out.append('    if (%s__hybrid_trap) %s;' % (item['mangled'], fail))
        out.append('    if (%s__mix_overflow) %s;' % (item['mangled'], fail))
        if ret == 'bool':
            out.append('    res = PyBool_FromLong((long)r);')
        else:
            out.append('    res = PyLong_FromLongLong((long long)r);')
        out.append('    if (!res) %s;' % fail)
    for i, w in updates:
        field = w['field']
        newval = 'u%d' % i
        if w['kind'] == 'bool':
            out.append('    PyObject *nv%d = PyBool_FromLong((long)%s);' % (i, newval))
        elif w['kind'] == 'float':
            out.append('    PyObject *nv%d = PyFloat_FromDouble(%s);' % (i, newval))
        else:
            out.append('    PyObject *nv%d = PyLong_FromLongLong((long long)%s);' % (i, newval))
        out.append('    if (!nv%d) { PyErr_Clear(); %s; }' % (i, fail))
        out.append('    if (PyObject_SetAttrString(obj, %s, nv%d) != 0) {' % (json.dumps(field), i))
        out.append('        Py_DECREF(nv%d); PyErr_Clear(); %s;' % (i, fail))
        out.append('    }')
        out.append('    Py_DECREF(nv%d);' % i)
    for fo in field_objs:
        out.append('    Py_XDECREF(%s);' % fo)
    for b in bufs:
        out.append('    PyMem_Free(%s);' % b)
    out.append('    return res;')
    out.append('fallback:')
    out.append('    PyErr_Clear();')
    for fo in field_objs:
        out.append('    Py_XDECREF(%s);' % fo)
    for b in bufs:
        out.append('    PyMem_Free(%s);' % b)
    out.append('    return ail_hybrid_fallback();')
    out.append('}')
    out.append('')
    return out


def _wrapper_source(module, items):
    out = [
        '#include <Python.h>',
        '#include <stdint.h>',
        '#include <stdlib.h>',
        '#include <string.h>',
        '',
        'typedef struct { const uint8_t *p; int64_t n; _Bool bytes; } ail_str;',
        'static PyObject *AilHybridFallback;',
        'void ail_mix_drain_out(void) { }',
        'static PyObject *ail_hybrid_fallback(void) {',
        '    PyErr_SetString(AilHybridFallback, "argument or result does not fit the AIL ABI");',
        '    return NULL;',
        '}',
        '',
    ]
    for item in items:
        callee = item['mangled'] + '__hybrid_call' if item.get('indexes') else item['mangled']
        out.append('extern %s;' % _c_proto(item, callee))
    out.append('')
    for item in items:
        if item.get('method'):
            out.extend(_method_wrapper_lines(item))
            continue
        if not item.get('expose', True):
            continue
        name = item['name']
        params = item['params']
        ret = item['ret']
        callee = item['mangled'] + '__hybrid_call' if item.get('indexes') else item['mangled']
        trap = item['mangled'] + '__hybrid_trap'
        # Owner decision D4 (2026-11-05): a call whose arguments include a container keeps the GIL.
        # The list is copied into a C buffer first, but the safe default is not to release while
        # other CPython threads may hold and mutate a container.  Scalar-only calls still release.
        hold = any(kind in _LIST for _p, kind in params)
        begin = [] if hold else ['    Py_BEGIN_ALLOW_THREADS']
        end = [] if hold else ['    Py_END_ALLOW_THREADS']
        out.append('static PyObject *ail_w_%s(PyObject *self, PyObject *args) {' % name)
        out.append('    PyObject *o[%d];' % max(1, len(params)))
        out.append('    if (PyTuple_GET_SIZE(args) != %d) return ail_hybrid_fallback();' % len(params))
        if item.get('indexes'):
            out.append('    extern __thread int %s;' % trap)
        # Every conversion failure after the declarations below must free whatever buffers an
        # earlier list argument already filled; `fallback:` does that.  When there are no buffers
        # the label is not emitted, so keep the direct return in that case.
        bufs = ['b%d' % i for i, (_p, kind) in enumerate(params)
                if kind in ('list[int]', 'list[float]')]
        fail = 'goto fallback' if bufs else 'return ail_hybrid_fallback()'
        for i, (p, kind) in enumerate(params):
            out.append('    o[%d] = PyTuple_GET_ITEM(args, %d);' % (i, i))
            # Declare every list buffer before any conversion loop.  A later loop can `goto
            # fallback` before its own declaration would have run; the label frees all of them,
            # so each must already be a valid pointer (NULL frees are no-ops).
            if kind == 'list[int]':
                out.append('    int64_t *b%d = NULL;' % i)
            elif kind == 'list[float]':
                out.append('    double *b%d = NULL;' % i)
        call = []
        for i, (p, kind) in enumerate(params):
            o = 'o[%d]' % i
            if kind in ('int', 'bool'):
                if kind == 'bool':
                    out.append('    if (!PyBool_Check(%s)) %s;' % (o, fail))
                    out.append('    int64_t a%d = PyObject_IsTrue(%s) ? 1 : 0;' % (i, o))
                else:
                    out.append('    if (!PyLong_CheckExact(%s)) %s;' % (o, fail))
                    out.append('    int ovf%d = 0; long long a%d = PyLong_AsLongLongAndOverflow(%s, &ovf%d);' % (i, i, o, i))
                    out.append('    if (ovf%d) %s;' % (i, fail))
                    out.append('    if (a%d == -1 && PyErr_Occurred()) { PyErr_Clear(); %s; }' % (i, fail))
                    out.append('    a%d = (int64_t)a%d;' % (i, i))
                call.append('a%d' % i)
            elif kind == 'float':
                out.append('    if (!PyFloat_CheckExact(%s)) %s;' % (o, fail))
                out.append('    double a%d = PyFloat_AsDouble(%s);' % (i, o))
                out.append('    if (a%d == -1.0 && PyErr_Occurred()) { PyErr_Clear(); %s; }' % (i, fail))
                call.append('a%d' % i)
            elif kind == 'str':
                out.append('    if (!PyUnicode_CheckExact(%s)) %s;' % (o, fail))
                out.append('    Py_ssize_t n%d = 0; const char *p%d = PyUnicode_AsUTF8AndSize(%s, &n%d);' % (i, i, o, i))
                out.append('    if (!p%d) { PyErr_Clear(); %s; }' % (i, fail))
                out.append('    ail_str a%d; a%d.p = (const uint8_t *)p%d; a%d.n = (int64_t)n%d; a%d.bytes = (PyUnicode_IS_ASCII(%s) ? 1 : 0);' % (i, i, i, i, i, i, o))
                call.append('a%d' % i)
            elif kind == 'list[int]':
                out.append('    if (!PyList_CheckExact(%s)) %s;' % (o, fail))
                out.append('    Py_ssize_t n%d = PyList_GET_SIZE(%s);' % (i, o))
                out.append('    b%d = n%d ? (int64_t *)PyMem_Malloc((size_t)n%d * sizeof(int64_t)) : NULL;' % (i, i, i))
                out.append('    if (n%d && !b%d) goto fallback;' % (i, i))
                out.append('    for (Py_ssize_t k%d = 0; k%d < n%d; k%d++) {' % (i, i, i, i))
                out.append('        PyObject *e%d = PyList_GET_ITEM(%s, k%d);' % (i, o, i))
                out.append('        if (!PyLong_CheckExact(e%d)) goto fallback;' % i)
                out.append('        int ovf%d = 0; long long v%d = PyLong_AsLongLongAndOverflow(e%d, &ovf%d);' % (i, i, i, i))
                out.append('        if (ovf%d) goto fallback;' % i)
                out.append('        if (v%d == -1 && PyErr_Occurred()) { PyErr_Clear(); goto fallback; }' % i)
                out.append('        b%d[k%d] = (int64_t)v%d;' % (i, i, i))
                out.append('    }')
                call.append('b%d' % i)
                call.append('(int64_t)n%d' % i)
            elif kind == 'list[float]':
                out.append('    if (!PyList_CheckExact(%s)) %s;' % (o, fail))
                out.append('    Py_ssize_t n%d = PyList_GET_SIZE(%s);' % (i, o))
                out.append('    b%d = n%d ? (double *)PyMem_Malloc((size_t)n%d * sizeof(double)) : NULL;' % (i, i, i))
                out.append('    if (n%d && !b%d) goto fallback;' % (i, i))
                out.append('    for (Py_ssize_t k%d = 0; k%d < n%d; k%d++) {' % (i, i, i, i))
                out.append('        PyObject *e%d = PyList_GET_ITEM(%s, k%d);' % (i, o, i))
                out.append('        if (!PyFloat_CheckExact(e%d)) goto fallback;' % i)
                out.append('        double v%d = PyFloat_AsDouble(e%d);' % (i, i))
                out.append('        if (v%d == -1.0 && PyErr_Occurred()) { PyErr_Clear(); goto fallback; }' % i)
                out.append('        b%d[k%d] = v%d;' % (i, i, i))
                out.append('    }')
                call.append('b%d' % i)
                call.append('(int64_t)n%d' % i)
        cargs = ', '.join(call)
        if ret == 'str':
            out.append('    int64_t need;')
            out.extend(begin)
            out.append('    need = %s(%s%sNULL, 0);' % (callee, cargs, ', ' if cargs else ''))
            out.extend(end)
            if item.get('indexes'):
                out.append('    if (%s) %s;' % (trap, fail))
            out.append('    if (need < 0) %s;' % fail)
            out.append('    uint8_t *sb = (uint8_t *)PyMem_Malloc((size_t)(need > 0 ? need : 1));')
            out.append('    if (!sb) {')
            for b in bufs:
                out.append('        PyMem_Free(%s);' % b)
            out.append('        return PyErr_NoMemory();')
            out.append('    }')
            out.extend(begin)
            out.append('    if (need > 0) %s(%s%s(void *)sb, need);' % (callee, cargs, ', ' if cargs else ''))
            out.extend(end)
            if item.get('indexes'):
                out.append('    if (%s) { PyMem_Free(sb); %s; }' % (trap, fail))
            out.append('    PyObject *res = PyUnicode_DecodeUTF8((const char *)sb, (Py_ssize_t)need, NULL);')
            out.append('    PyMem_Free(sb);')
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    if (!res) { PyErr_Clear(); return ail_hybrid_fallback(); }')
            out.append('    return res;')
        elif ret == 'float':
            out.append('    double r;')
            out.extend(begin)
            out.append('    r = %s(%s);' % (callee, cargs))
            out.extend(end)
            if item.get('indexes'):
                out.append('    if (%s) %s;' % (trap, fail))
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    return PyFloat_FromDouble(r);')
        else:
            out.append('    extern __thread int %s__mix_overflow;' % item['mangled'])
            out.append('    int64_t r; int ovf;')
            out.extend(begin)
            out.append('    r = %s(%s);' % (callee, cargs))
            out.append('    ovf = %s__mix_overflow;' % item['mangled'])
            out.extend(end)
            if item.get('indexes'):
                out.append('    if (%s) %s;' % (trap, fail))
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    if (ovf) return ail_hybrid_fallback();')
            if ret == 'bool':
                out.append('    return PyBool_FromLong((long)r);')
            else:
                out.append('    return PyLong_FromLongLong((long long)r);')
        if bufs:
            out.append('fallback:')
            for b in bufs:
                out.append('    PyMem_Free(%s);' % b)
            out.append('    return ail_hybrid_fallback();')
        out.append('}')
        out.append('')
    out.append('static PyMethodDef ail_methods[] = {')
    for item in items:
        if not item.get('expose', True):
            continue
        out.append('    {"%s", ail_w_%s, METH_VARARGS, NULL},' % (item['name'], item['name']))
    out.append('    {NULL, NULL, 0, NULL}')
    out.append('};')
    out.append('static struct PyModuleDef ail_module = {PyModuleDef_HEAD_INIT, "%s", NULL, -1, ail_methods};' % module)
    out.append('PyMODINIT_FUNC PyInit_%s(void) {' % module)
    out.append('    PyObject *m = PyModule_Create(&ail_module);')
    out.append('    if (!m) return NULL;')
    out.append('    AilHybridFallback = PyErr_NewException("%s.Fallback", NULL, NULL);' % module)
    out.append('    if (!AilHybridFallback) { Py_DECREF(m); return NULL; }')
    out.append('    Py_INCREF(AilHybridFallback);')
    out.append('    PyModule_AddObject(m, "Fallback", AilHybridFallback);')
    out.append('    return m;')
    out.append('}')
    return '\n'.join(out) + '\n'


def _insertion_point(tree):
    """After the module docstring and any `from __future__` imports, so the preamble is legal."""
    body = tree.body
    at = 0
    i = 0
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        at = body[0].end_lineno or 0
        i = 1
    while i < len(body) and isinstance(body[i], ast.ImportFrom) and body[i].module == '__future__':
        at = body[i].end_lineno or at
        i += 1
    return at


def _preamble(module, original_path):
    _text = (
        '\n# --- AIL CPython hybrid (generated preamble) ---\n'
        'import os as _ail_hybrid_os\n'
        'import sys as _ail_hybrid_sys\n'
        '_ail_hybrid_source = __AIL_SOURCE__\n'
        '_ail_hybrid_source_dir = _ail_hybrid_os.path.dirname(_ail_hybrid_source)\n'
        'if _ail_hybrid_source_dir and _ail_hybrid_source_dir not in _ail_hybrid_sys.path:\n'
        '    _ail_hybrid_sys.path.insert(0, _ail_hybrid_source_dir)\n'
        'if __name__ == "__main__" and _ail_hybrid_sys.argv:\n'
        '    _ail_hybrid_sys.argv[0] = _ail_hybrid_source\n'
        '__file__ = _ail_hybrid_source\n'
        'try:\n'
        '    import __AIL_MODULE__ as _ail_hybrid_native\n'
        'except Exception:\n'
        '    _ail_hybrid_native = None\n'
        'def _ail_hybrid_invoke(_native, _original, _pos, _kw, _varargs, _varkw):\n'
        '    if _native is not None and not _varkw:\n'
        '        try:\n'
        '            return _native(*_pos, *_kw.values(), *_varargs)\n'
        '        except _ail_hybrid_native.Fallback:\n'
        '            pass\n'
        '    return _original(*_pos, *_varargs, **_kw, **_varkw)\n'
        'def _ail_hybrid_make(_native, _original):\n'
        '    if _native is None or _original is None:\n'
        '        return _original\n'
        '    try:\n'
        '        import inspect as _ail_hybrid_inspect\n'
        '        _params = list(_ail_hybrid_inspect.signature(_original).parameters.values())\n'
        '    except Exception:\n'
        '        return _original\n'
        '    _posonly, _pos, _kwonly = [], [], []\n'
        '    _vararg = _varkw = None\n'
        '    for _p in _params:\n'
        '        if _p.kind == _ail_hybrid_inspect.Parameter.POSITIONAL_ONLY:\n'
        '            _posonly.append(_p)\n'
        '        elif _p.kind == _ail_hybrid_inspect.Parameter.POSITIONAL_OR_KEYWORD:\n'
        '            _pos.append(_p)\n'
        '        elif _p.kind == _ail_hybrid_inspect.Parameter.KEYWORD_ONLY:\n'
        '            _kwonly.append(_p)\n'
        '        elif _p.kind == _ail_hybrid_inspect.Parameter.VAR_POSITIONAL:\n'
        '            _vararg = _p\n'
        '        elif _p.kind == _ail_hybrid_inspect.Parameter.VAR_KEYWORD:\n'
        '            _varkw = _p\n'
        '    _decl = [p.name for p in _posonly]\n'
        '    if _posonly:\n'
        '        _decl.append("/")\n'
        '    _decl.extend(p.name for p in _pos)\n'
        '    if _vararg is not None:\n'
        '        _decl.append("*" + _vararg.name)\n'
        '    elif _kwonly:\n'
        '        _decl.append("*")\n'
        '    _decl.extend(p.name for p in _kwonly)\n'
        '    if _varkw is not None:\n'
        '        _decl.append("**" + _varkw.name)\n'
        '    _posnames = [p.name for p in _posonly + _pos]\n'
        '    if len(_posnames) == 1:\n'
        '        _postuple = "(" + _posnames[0] + ",)"\n'
        '    else:\n'
        '        _postuple = "(" + ", ".join(_posnames) + ")"\n'
        '    _kwtext = "{" + ", ".join("%r: %s" % (p.name, p.name) for p in _kwonly) + "}"\n'
        '    _varkwtext = _varkw.name if _varkw is not None else "{}"\n'
        '    _varargtext = _vararg.name if _vararg is not None else "()"\n'
        '    # The generated body needs three helper names from its globals.  A parameter may have\n'
        '    # any of the obvious names, so pick spellings the parameter list cannot shadow.\n'
        '    _taken = {p.name for p in _params}\n'
        '    _helpers = {}\n'
        '    for _role in ("invoke", "native", "original"):\n'
        '        _nm = "__ail_hybrid_" + _role\n'
        '        while _nm in _taken:\n'
        '            _nm += "_"\n'
        '        _taken.add(_nm)\n'
        '        _helpers[_role] = _nm\n'
        '    _src = ("def _ail_hybrid_call(%s):\\n"\n'
        '            "    return %s(%s, %s, %s, %s, %s, %s)\\n"\n'
        '            % (", ".join(_decl), _helpers["invoke"], _helpers["native"],\n'
        '               _helpers["original"], _postuple, _kwtext, _varargtext, _varkwtext))\n'
        '    _namespace = {_helpers["invoke"]: _ail_hybrid_invoke,\n'
        '                  _helpers["native"]: _native,\n'
        '                  _helpers["original"]: _original}\n'
        '    exec(_src, _namespace)\n'
        '    _call = _namespace["_ail_hybrid_call"]\n'
        '    _call.__name__ = _original.__name__\n'
        '    _call.__qualname__ = _original.__qualname__\n'
        '    _call.__doc__ = _original.__doc__\n'
        '    _call.__module__ = _original.__module__\n'
        '    _call.__annotations__ = getattr(_original, "__annotations__", {})\n'
        '    _call.__defaults__ = getattr(_original, "__defaults__", None)\n'
        '    _call.__kwdefaults__ = getattr(_original, "__kwdefaults__", None)\n'
        '    try:\n'
        '        _call.__dict__.update(_original.__dict__)\n'
        '    except Exception:\n'
        '        pass\n'
        '    # CPython introspection sees the original code layout, including its local names.\n'
        '    # `co_nlocals` must be updated with `co_varnames` (CodeType rejects a mismatch); only\n'
        '    # the wrapper\'s parameter slots are ever loaded, so the extra locals are inert.\n'
        '    try:\n'
        '        _oc = _original.__code__\n'
        '        _kw = {"co_name": _oc.co_name, "co_varnames": _oc.co_varnames,\n'
        '               "co_nlocals": len(_oc.co_varnames),\n'
        '               "co_filename": _oc.co_filename, "co_firstlineno": _oc.co_firstlineno}\n'
        '        if hasattr(_oc, "co_qualname"):\n'
        '            _kw["co_qualname"] = _oc.co_qualname\n'
        '        _call.__code__ = _call.__code__.replace(**_kw)\n'
        '    except Exception:\n'
        '        pass\n'
        '    return _call\n'
        'if _ail_hybrid_native is None:\n'
        '    def _ail_hybrid_make(_native, _original):\n'
        '        return _original\n'
        '# --- original program follows ---\n\n'
    )
    return _text.replace('__AIL_MODULE__', module).replace('__AIL_SOURCE__', repr(str(original_path)))


def _hybrid_source(source, tree, module, names, original_path, method_rebinds=()):
    """Original text plus a preamble and one rebinding after each accelerated top-level def."""
    lines = source.splitlines(keepends=True)
    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'
    funcs = _top_level_functions(tree)
    edits = []
    at = _insertion_point(tree)
    edits.append((at, 0, _preamble(module, original_path)))
    for name in names:
        fn = funcs.get(name)
        if fn is not None and getattr(fn, 'end_lineno', None):
            text = ('try:\n'
                    '    %s = _ail_hybrid_make(_ail_hybrid_native.%s, %s)\n'
                    'except Exception:\n'
                    '    pass\n' % (name, name, name))
            edits.append((fn.end_lineno, 0, text))
    for class_name, method_name, kernel, end_lineno in method_rebinds:
        text = ('try:\n'
                '    %s.%s = _ail_hybrid_make(_ail_hybrid_native.%s, %s.%s)\n'
                'except Exception:\n'
                '    pass\n' % (class_name, method_name, kernel,
                              class_name, method_name))
        edits.append((end_lineno, 0, text))
    edits.sort(key=lambda e: e[0], reverse=True)
    for at, _off, text in edits:
        lines.insert(at, text)
    return ''.join(lines)


def _compile(items, units, module, out_dir):
    from pipeline import compiler, opt_flags
    cc = compiler()
    extra = ['-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd',
             '-fno-asynchronous-unwind-tables']
    include = sysconfig.get_paths().get('include') or sysconfig.get_path('include')
    cflags = [cc, *opt_flags(), *extra, '-fPIC', '-pthread', '-I' + include]
    objects = []
    for i, item in enumerate(items):
        csrc = next(u[2] for u in units if u[1] == item['name'])
        if item.get('indexes'):
            csrc = _trap_patch(csrc, item['mangled'])
        # The mixed-mode overflow signal is a per-function global.  The hybrid releases the GIL
        # around every native call, so two threads can otherwise reset/read each other's flag and
        # a truncated int could escape.  Give the hybrid's copy of the unit a thread-local flag;
        # the wrapper's matching `extern` below is thread-local too.
        csrc = re.sub(r'(?m)^extern int (%s__mix_overflow);$' % re.escape(item['mangled']),
                      r'extern __thread int \1;', csrc)
        csrc = re.sub(r'(?m)^int (%s__mix_overflow) = 0;$' % re.escape(item['mangled']),
                      r'__thread int \1 = 0;', csrc)
        # The int64-overflow escape is per-call as well: the buffer and the save pointer must
        # belong to the calling thread, or two concurrent overflow fallbacks restore each
        # other's cleanup state or longjmp through the other thread's frame (SIGABRT).
        csrc = re.sub(r'(?m)^static jmp_buf (%s__mix_jmp);$' % re.escape(item['mangled']),
                      r'static __thread jmp_buf \1;', csrc)
        csrc = re.sub(r'(?m)^static ([A-Za-z_][A-Za-z0-9_]* \*%s__mix_savep);$'
                      % re.escape(item['mangled']), r'static __thread \1;', csrc)
        cpath = out_dir / ('%s_unit%d.c' % (module, i))
        opath = out_dir / ('%s_unit%d.o' % (module, i))
        cpath.write_text(csrc, encoding='utf-8')
        r = subprocess.run([*cflags, '-c', '-o', str(opath), str(cpath)], capture_output=True, text=True)
        if r.returncode:
            for p in out_dir.glob(module + '_unit*'):
                try: p.unlink()
                except OSError: pass
            raise RuntimeError('typed unit %r: %s' % (item['name'], r.stderr[-1500:]))
        objects.append(str(opath))
    wrapper = out_dir / ('%s_wrapper.c' % module)
    wrapper.write_text(_wrapper_source(module, items), encoding='utf-8')
    so = out_dir / (module + _EXT_SUFFIX)
    r = subprocess.run([cc, *opt_flags(), *extra, '-fPIC', '-pthread', '-I' + include, '-shared', '-o', str(so),
                        str(wrapper)] + objects + ['-lm'], capture_output=True, text=True)
    if r.returncode:
        for p in list(out_dir.glob(module + '_unit*')) + [wrapper]:
            try: p.unlink()
            except OSError: pass
        raise RuntimeError('extension link: %s' % r.stderr[-1500:])
    for p in out_dir.glob(module + '_unit*'):
        try:
            p.unlink()
        except OSError:
            pass
    try:
        wrapper.unlink()
    except OSError:
        pass
    return so


def build(source_path, output_dir):
    """Build a CPython hybrid for `source_path` into `output_dir`; return the report dict."""
    source_path = Path(source_path).resolve()
    output_dir = Path(output_dir).resolve()
    source = source_path.read_text(encoding='utf-8')
    tree = ast.parse(source, filename=str(source_path))
    stem = source_path.stem
    module = _module_name(stem)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        'schema': 'ail.cpython_hybrid/2',
        'source': str(source_path),
        'python': sys.version.split()[0],
        'module': module,
        'accelerated': [],
        'rejected': {},
        'extension': None,
        'run_file': stem + '_run.py',
        'python_file': stem + '.py',
    }
    chosen = {}
    method_rebinds = []
    try:
        plan = _method_kernels(tree)
        kernel_nodes = _method_kernel_nodes(plan)
        if kernel_nodes:
            analysis_source = source.rstrip('\n') + '\n\n' + '\n\n'.join(
                ast.unparse(node) for node in kernel_nodes) + '\n'
            analysis_tree = ast.parse(analysis_source, filename=str(source_path))
        else:
            analysis_source, analysis_tree = source, tree
        units_report, facts = _analysis(analysis_source)
        chosen, rejected = _select(analysis_source, analysis_tree, units_report, facts)
        units = units_report.get('mix_units') or []
        unit_names = {u[1] for u in units}
        kernel_owner = {}
        field_kernel_owner = {}
        for class_name, class_plan in plan.items():
            for method_name, info in class_plan['methods'].items():
                if 'reason' in info:
                    rejected['%s.%s' % (class_name, method_name)] = info['reason']
                    continue
                kernel_owner[info['kernel_name']] = (class_name, method_name, info)
                for field, node in info['field_kernels'].items():
                    field_kernel_owner[node.name] = (class_name, method_name, field)
            if class_plan['reason'] is not None:
                for stmt in class_plan['class'].body:
                    if isinstance(stmt, ast.FunctionDef):
                        rejected['%s.%s' % (class_name, stmt.name)] = class_plan['reason']
        # The lifted kernels are not module functions of their own; they are wrapped below.
        items = [chosen[name] for name in sorted(chosen)
                 if name in unit_names and name not in kernel_owner
                 and name not in field_kernel_owner]
        accelerated = [item['name'] for item in items]
        for class_name, class_plan in plan.items():
            for method_name, info in class_plan['methods'].items():
                if 'reason' in info:
                    continue
                kernel = info['kernel_name']
                needed = [info['field_kernels'][f].name for f in sorted(info['field_kernels'])]
                label = '%s.%s' % (class_name, method_name)
                if kernel not in chosen or kernel not in unit_names:
                    rejected[label] = rejected.get(kernel) or (
                        'the typed clone is not wired to the hybrid ABI, stays in CPython')
                    continue
                if any(name not in chosen or name not in unit_names for name in needed):
                    rejected[label] = 'a field value is not a typed clone, stays in CPython'
                    continue
                result = dict(chosen[kernel])
                result['indexes'] = True
                fields_meta = []
                field_kind = dict(class_plan['fields'])
                field_index = {field: i for i, field in enumerate(info['needed'])}
                for field in info['needed']:
                    fields_meta.append((field_index[field], field, field_kind[field]))
                writes_meta = []
                for field in sorted(info['writes']):
                    fk = info['field_kernels'][field]
                    writes_meta.append({'field': field, 'kind': field_kind[field],
                                        'index': field_index[field],
                                        'mangled': chosen[fk.name]['mangled'],
                                        'indexes': True})
                    field_item = dict(chosen[fk.name])
                    field_item['indexes'] = True
                    field_item['expose'] = False
                    items.append(field_item)
                result['method'] = {'class': class_name, 'method': method_name,
                                    'fields': fields_meta, 'writes': writes_meta}
                items.append(result)
                accelerated.append(label)
                method_rebinds.append((class_name, method_name, kernel,
                                       class_plan['class'].end_lineno))
                rejected.pop(kernel, None)
                for name in needed:
                    rejected.pop(name, None)
        # Kernel-only names never appear in the report; their method names already carry them.
        report['rejected'] = {k: v for k, v in rejected.items()
                              if k not in kernel_owner and k not in field_kernel_owner}
        if items:
            so = _compile(items, units, module, output_dir)
            report['extension'] = so.name
            report['accelerated'] = sorted(accelerated)
        elif units:
            report['note'] = 'the typed functions were not safe to wrap; the program runs in CPython'
    except Exception as error:
        report['note'] = 'no extension: %s' % error

    # Always keep an unmodified copy and a runnable hybrid copy.  `prog_run.py` is the file the
    # task names; the `<stem>.py` copy stays for callers of the earlier --cpython prototype.
    (output_dir / (stem + '.orig.py')).write_text(source, encoding='utf-8')
    hybrid = _hybrid_source(source, tree, module, report['accelerated'], source_path,
                            method_rebinds)
    (output_dir / report['run_file']).write_text(hybrid, encoding='utf-8')
    legacy = output_dir / report['python_file']
    if legacy.resolve() != source_path:
        legacy.write_text(hybrid, encoding='utf-8')
    launcher = output_dir / stem
    launcher.write_text('#!/bin/sh\nexec "${AIL_PYTHON:-python3}" "$(dirname "$0")/%s" "$@"\n'
                        % report['run_file'], encoding='utf-8')
    launcher.chmod(0o755)
    (output_dir / 'build.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n',
                                           encoding='utf-8')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='build a CPython hybrid: typed functions become an extension module, '
                    'everything else runs in CPython')
    parser.add_argument('source', metavar='SOURCE')
    parser.add_argument('-o', '--out', metavar='DIR')
    args = parser.parse_args()
    source = Path(args.source)
    output = Path(args.out) if args.out else source.parent / (source.stem + '_hybrid')
    report = build(source, output)
    print('built %s: %d function(s) accelerated' % (output, len(report.get('accelerated') or [])))
    print('run %s' % (output / report['run_file']))
