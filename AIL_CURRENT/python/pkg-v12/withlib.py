# -*- coding: utf-8 -*-
"""`with` statements and contextlib on the general (boxed) path (called from pyboxed2.Compiler.compile, general path only).

A `with` is lowered to the statements PEP 343 describes, on the program's own classes:

    with EXPR as VAR:            m = EXPR; VAR = m.__enter__(); done = False
        BODY                     try:
                                     BODY
                                 except Exception as e:
                                     done = True
                                     if not m.__exit__(_AilExcType("ValueError"), e, None): raise
                                 finally:
                                     if not done: m.__exit__(None, None, None)

so `return` / `break` / `continue` out of BODY call __exit__ once, an exception goes to __exit__ and is raised again
unless __exit__ returns true, and several items nest left to right.

* `with open(...)` and `with f:` on a file variable are left to filelower.py (it runs first and keeps the other items).
* `with suppress(A, B):` (contextlib) is `try: BODY / except (A, B): pass`; `suppress` with something that is not a
  plain list of exception names, or with `as`, is refused by name.
* `@contextmanager` on a def or a method: the generator is renamed `_ail_cm_<name>` and its `yield` statements become
  `t = yield v; if t is not None: raise t`, and the def keeps its name and parameters and returns `_AilGenCM(generator)`
  (prelude_with.py), whose __exit__ throws the exception into the generator by `send` (there is no generator.throw):
  a `try: yield ... finally:` or `except` around the yield behaves as in CPython.
* `closing(x)` and `nullcontext(v)`. Not built, refused by name: ExitStack, redirect_stdout, the other names.

Differences from CPython (declared in DIFFERENCES.md): __exit__'s first argument is a stand-in object with `__name__`
that prints as `<class 'X'>` (there are no class values here; `exc_type is X`, `issubclass(exc_type, X)` and
`exc_type in (A, B)` inside __exit__ are rewritten to compare the class name of the exception instead); an exception
that is not an Exception (SystemExit ...) leaves the body without calling __exit__ with its class (it gets None); a
manager without __enter__ / __exit__ raises AttributeError, not TypeError.
"""
import ast
import copy
import os

import stdlib5
from stdlib4 import Refused, refuse

HANDLED = {'contextmanager', 'suppress', 'closing', 'nullcontext'}
HERE = os.path.dirname(os.path.abspath(__file__))
BUILTIN_EXC = {'BaseException', 'Exception', 'ArithmeticError', 'AssertionError', 'AttributeError', 'EOFError',
               'FloatingPointError', 'IndexError', 'KeyError', 'LookupError', 'MemoryError', 'NameError',
               'NotImplementedError', 'OSError', 'OverflowError', 'RecursionError', 'RuntimeError', 'StopIteration',
               'SystemExit', 'TypeError', 'ValueError', 'ZeroDivisionError', 'UnicodeError', 'UnicodeDecodeError',
               'UnicodeEncodeError', 'FileNotFoundError', 'FileExistsError', 'PermissionError', 'IsADirectoryError',
               'NotADirectoryError', 'TimeoutError', 'ConnectionError', 'KeyboardInterrupt'}


def N(name, store=False):
    return ast.Name(id=name, ctx=ast.Store() if store else ast.Load())


def call(func, args=()):
    return ast.Call(func=func, args=list(args), keywords=[])


def method(obj, name, args=()):
    return call(ast.Attribute(value=obj, attr=name, ctx=ast.Load()), args)


class Lower(ast.NodeTransformer):
    def __init__(self, tree, binder):
        self.tree = tree
        self.binder = binder
        self.count = 0
        self.used = False
        self.cm = False
        self.classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}

    def fresh(self, stem):
        self.count += 1
        return '_ail_%s%d' % (stem, self.count)

    # ---- with ------------------------------------------------------------------------------------
    def visit_With(self, node):
        self.generic_visit(node)
        body = node.body
        for item in reversed(node.items):
            body = self.one(node, item, body)
        return body

    def is_suppress(self, expr):
        return isinstance(expr, ast.Call) and self.binder.attr(expr.func) == 'suppress'

    def one(self, node, item, body):
        expr, target = item.context_expr, item.optional_vars
        if self.is_suppress(expr):
            if target is not None:
                refuse(node, 'contextlib.suppress(...) as %s: the manager object is not built' % ast.unparse(target))
            names = []
            for arg in expr.args:
                if isinstance(arg, ast.Starred) or not isinstance(arg, (ast.Name, ast.Attribute)):
                    refuse(arg, 'contextlib.suppress: name the exception classes (suppress(KeyError, IndexError))')
                names.append(arg)
            if expr.keywords:
                refuse(expr, 'contextlib.suppress takes exception classes only')
            if not names:
                return body
            self.used = True
            handler = ast.ExceptHandler(type=names[0] if len(names) == 1 else ast.Tuple(elts=names, ctx=ast.Load()),
                                        name=None, body=[ast.Pass()])
            return [ast.copy_location(ast.Try(body=body, handlers=[handler], orelse=[], finalbody=[]), node)]
        self.used = True
        m, done, e = self.fresh('wm'), self.fresh('wd'), self.fresh('we')
        enter = method(N(m), '__enter__')
        jump = self.fresh('wj')
        wrapped = rewrite_jumps(body, jump)
        after = []
        if wrapped:
            # a break / continue of the loop around the `with` cannot leave a try/finally here: the body runs in a
            # one-shot loop, the jump becomes a flag and a break, and the flag is acted on after the try
            body = [ast.While(test=ast.Constant(value=True), body=body + [ast.Break()], orelse=[])]
            after = [ast.If(test=ast.Compare(left=N(jump), ops=[ast.Eq()], comparators=[ast.Constant(value=1)]),
                            body=[ast.Break()], orelse=[]),
                     ast.If(test=ast.Compare(left=N(jump), ops=[ast.Eq()], comparators=[ast.Constant(value=2)]),
                            body=[ast.Continue()], orelse=[])]
        stmts = [ast.Assign(targets=[N(m, True)], value=expr)]
        if wrapped:
            stmts.append(ast.Assign(targets=[N(jump, True)], value=ast.Constant(value=0)))
        if target is None:
            stmts.append(ast.Expr(value=enter))
        else:
            stmts.append(ast.Assign(targets=[target], value=enter))
        stmts.append(ast.Assign(targets=[N(done, True)], value=ast.Constant(value=False)))
        exc_type = call(N('_AilExcType'), [call(N('_ail_exc_name'), [N(e)])])
        handler = ast.ExceptHandler(
            type=N('Exception'), name=e,
            body=[ast.Assign(targets=[N(done, True)], value=ast.Constant(value=True)),
                  ast.If(test=ast.UnaryOp(op=ast.Not(), operand=method(N(m), '__exit__', [exc_type, N(e), ast.Constant(value=None)])),
                         body=[ast.Raise(exc=None, cause=None)], orelse=[])])
        final = [ast.If(test=ast.UnaryOp(op=ast.Not(), operand=N(done)),
                        body=[ast.Expr(value=method(N(m), '__exit__', [ast.Constant(value=None)] * 3))], orelse=[])]
        stmts.append(ast.Try(body=body, handlers=[handler], orelse=[], finalbody=final))
        stmts.extend(after)
        for each in stmts:
            ast.copy_location(each, node)
        return stmts

    # ---- @contextmanager ---------------------------------------------------------------------
    def is_cm_decorator(self, dec):
        return self.binder.attr(dec) == 'contextmanager'

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        return self.maybe_cm(node, None)

    def visit_ClassDef(self, node):
        body = []
        for stmt in node.body:
            new = self.visit(stmt) if not isinstance(stmt, ast.FunctionDef) else self.method_cm(stmt)
            body.extend(new if isinstance(new, list) else [new])
        node.body = body
        return node

    def method_cm(self, node):
        self.generic_visit(node)
        return self.maybe_cm(node, 'self')

    def maybe_cm(self, node, owner):
        marked = [d for d in node.decorator_list if self.is_cm_decorator(d)]
        if not marked:
            return node
        if len(node.decorator_list) != 1:
            refuse(node, 'def %s: a decorator next to @contextmanager is not built' % node.name)
        a = node.args
        if a.posonlyargs or a.vararg or a.kwarg or a.kwonlyargs:
            refuse(node, 'def %s: a @contextmanager function takes plain positional parameters here' % node.name)
        yields = own_yields(node)
        if not yields:
            refuse(node, 'def %s: @contextmanager on a function with no yield' % node.name)
        self.used = self.cm = True
        inner_name = '_ail_cm_' + node.name
        inner = copy.deepcopy(node)
        inner.name = inner_name
        inner.decorator_list = []
        inner.returns = None
        inner.args.defaults = []
        t = self.fresh('t')
        inner.body = Yields(t).visit_block(inner.body)
        names = [p.arg for p in a.args]
        if owner:
            if not names or names[0] != 'self':
                refuse(node, 'def %s: a @contextmanager method takes self first' % node.name)
            target = ast.Attribute(value=N('self'), attr=inner_name, ctx=ast.Load())
            passed = [N(n) for n in names[1:]]
        else:
            target = N(inner_name)
            passed = [N(n) for n in names]
        wrapper = copy.deepcopy(node)
        wrapper.decorator_list = []
        wrapper.returns = None
        wrapper.body = [ast.Return(value=call(N('_AilGenCM'), [call(target, passed)]))]
        for each in (inner, wrapper):
            ast.copy_location(each, node)
        return [inner, wrapper]


def rewrite_jumps(stmts, flag):
    """In `stmts` (in place) every break / continue that belongs to the loop around the block becomes
    `flag = 1 (2); break`. Returns whether there was one."""
    found = [False]

    def block(items):
        out = []
        for stmt in items:
            if isinstance(stmt, (ast.Break, ast.Continue)):
                found[0] = True
                out.append(ast.copy_location(ast.Assign(
                    targets=[N(flag, True)], value=ast.Constant(value=1 if isinstance(stmt, ast.Break) else 2)), stmt))
                out.append(ast.copy_location(ast.Break(), stmt))
                continue
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.append(stmt)
                continue
            if isinstance(stmt, (ast.For, ast.While, ast.AsyncFor)):
                stmt.orelse = block(stmt.orelse)               # the else of an inner loop belongs to the outer one
            else:
                for field in ('body', 'orelse', 'finalbody'):
                    if isinstance(getattr(stmt, field, None), list):
                        setattr(stmt, field, block(getattr(stmt, field)))
                for handler in getattr(stmt, 'handlers', []) or []:
                    handler.body = block(handler.body)
                for case in getattr(stmt, 'cases', []) or []:
                    case.body = block(case.body)
            out.append(stmt)
        return out
    stmts[:] = block(stmts)
    return found[0]


def own_yields(fn):
    """The yield nodes of a def itself (not of a def, lambda or class inside it)."""
    found = []

    def walk(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(child, (ast.Yield, ast.YieldFrom)):
                found.append(child)
            walk(child)
    for stmt in fn.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            walk(ast.Module(body=[stmt], type_ignores=[]))
    return found


class Yields:
    """`yield v` as a statement (or `x = yield v`) becomes the yield and a raise of what send() brought in."""

    def __init__(self, temp):
        self.temp = temp

    def check(self, at):
        return ast.copy_location(ast.If(
            test=ast.Compare(left=N(self.temp), ops=[ast.IsNot()], comparators=[ast.Constant(value=None)]),
            body=[ast.Raise(exc=N(self.temp), cause=None)], orelse=[]), at)

    def visit_block(self, stmts):
        out = []
        for stmt in stmts:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Yield):
                out.append(ast.copy_location(ast.Assign(targets=[N(self.temp, True)], value=stmt.value), stmt))
                out.append(self.check(stmt))
                continue
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Yield):
                out.append(ast.copy_location(ast.Assign(targets=[N(self.temp, True)], value=stmt.value), stmt))
                out.append(self.check(stmt))
                out.append(ast.copy_location(ast.Assign(targets=stmt.targets, value=ast.Constant(value=None)), stmt))
                continue
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.append(stmt)
                continue
            for field in ('body', 'orelse', 'finalbody'):
                if isinstance(getattr(stmt, field, None), list):
                    setattr(stmt, field, self.visit_block(getattr(stmt, field)))
            for handler in getattr(stmt, 'handlers', []) or []:
                handler.body = self.visit_block(handler.body)
            for each in ast.walk(stmt) if not isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try, ast.With)) \
                    else expression_parts(stmt):
                if isinstance(each, (ast.Yield, ast.YieldFrom)):
                    refuse(stmt, 'a @contextmanager generator: `yield` is built as a statement (`yield v` or `x = yield v`)')
            out.append(stmt)
        return out


def expression_parts(stmt):
    """The expressions of a compound statement's own header (not its blocks)."""
    heads = []
    if isinstance(stmt, (ast.If, ast.While)):
        heads = [stmt.test]
    elif isinstance(stmt, ast.For):
        heads = [stmt.iter, stmt.target]
    elif isinstance(stmt, ast.With):
        heads = [i.context_expr for i in stmt.items]
    for head in heads:
        yield from ast.walk(head)
    for handler in getattr(stmt, 'handlers', []) or []:
        if handler.type is not None:
            yield from ast.walk(handler.type)


class ExitArgs(ast.NodeTransformer):
    """Inside `def __exit__(self, exc_type, exc, tb)`: `issubclass(exc_type, X)`, `exc_type is X`, `exc_type == X`,
    `exc_type in (A, B)` compare the exception instance's class name (there are no class values here)."""

    def __init__(self, ty, ex, classes):
        self.ty, self.ex, self.classes = ty, ex, classes

    def isclass(self, node):
        return isinstance(node, ast.Name) and (node.id in BUILTIN_EXC or node.id in self.classes)

    def is_ty(self, node):
        return isinstance(node, ast.Name) and node.id == self.ty

    def named(self, cls):
        return ast.Compare(left=call(N('_ail_exc_name'), [N(self.ex)]), ops=[ast.Eq()],
                           comparators=[ast.Constant(value=cls.id)])

    def present(self, test):
        return ast.BoolOp(op=ast.And(), values=[
            ast.Compare(left=N(self.ex), ops=[ast.IsNot()], comparators=[ast.Constant(value=None)]), test])

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == 'issubclass' and len(node.args) == 2 \
                and self.is_ty(node.args[0]):
            second = node.args[1]
            if isinstance(second, ast.Tuple) and all(self.isclass(e) for e in second.elts) or self.isclass(second):
                return ast.copy_location(self.present(call(N('isinstance'), [N(self.ex), second])), node)
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) == 1 and self.is_ty(node.left):
            op, right = node.ops[0], node.comparators[0]
            if isinstance(op, (ast.Is, ast.Eq, ast.IsNot, ast.NotEq)) and self.isclass(right):
                test = self.present(self.named(right))
                if isinstance(op, (ast.IsNot, ast.NotEq)):
                    test = ast.UnaryOp(op=ast.Not(), operand=test)
                return ast.copy_location(test, node)
            if isinstance(op, (ast.In, ast.NotIn)) and isinstance(right, (ast.Tuple, ast.List)) \
                    and all(self.isclass(e) for e in right.elts):
                test = self.present(ast.Compare(left=call(N('_ail_exc_name'), [N(self.ex)]), ops=[ast.In()],
                                                comparators=[ast.Tuple(elts=[ast.Constant(value=e.id) for e in right.elts],
                                                                       ctx=ast.Load())]))
                if isinstance(op, ast.NotIn):
                    test = ast.UnaryOp(op=ast.Not(), operand=test)
                return ast.copy_location(test, node)
        return node


def rewrite(tree):
    """Lower the `with` statements and contextlib names of `tree` (in place); returns the prelude source to add, or ''.
    Raises stdlib4.Refused for a use that is not built."""
    has_with = any(isinstance(n, ast.With) for n in ast.walk(tree))
    has_cl = any((isinstance(n, ast.Import) and any(a.name == 'contextlib' for a in n.names))
                 or (isinstance(n, ast.ImportFrom) and n.module == 'contextlib') for n in tree.body)
    if not has_with and not has_cl:
        return ''
    binder = stdlib5.take_imports(tree, 'contextlib', HANDLED,
                                  unknown='contextmanager, suppress, closing and nullcontext are built')
    lower = Lower(tree, binder)
    # closing(x) / nullcontext(v) as a value: the classes of the prelude
    need = set()

    def fix(node):
        found = binder.attr(node)
        if found == 'closing':
            need.add('_AilClosing')
            return N('_AilClosing')
        if found == 'nullcontext':
            need.add('_AilNullContext')
            return N('_AilNullContext')
        return None
    tree.body = [stdlib5.Replace(fix).visit(s) for s in tree.body]
    new_body = []
    for stmt in tree.body:
        res = lower.visit(stmt)
        new_body.extend(res if isinstance(res, list) else [res])
    tree.body = new_body
    classes = lower.classes
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '__exit__' and len(node.args.args) >= 3:
            ty, ex = node.args.args[1].arg, node.args.args[2].arg
            node.body = [ExitArgs(ty, ex, classes).visit(s) for s in node.body]
    stdlib5.leftover(tree, binder, 'contextmanager, suppress, closing and nullcontext are built')
    if not (lower.used or need):
        return ''
    roots = set(need)
    if lower.used:
        roots.add('_AilExcType')
    if lower.cm:
        roots.add('_AilGenCM')
    source = open(os.path.join(HERE, 'prelude_with.py'), encoding='utf-8').read()
    return stdlib5.shake(source, roots)
