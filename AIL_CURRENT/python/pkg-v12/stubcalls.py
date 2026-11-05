# -*- coding: utf-8 -*-
"""Stub-typed stdlib calls on the general path (typeshed2).

`unified._etype` asks `call_type` about an `ast.Call`.  A call whose callee resolves to a vendored
stdlib function and whose typeshed return is `int`, `float` or `bool` (with no disagreeing
overload set) becomes that scalar type.  The emitter then runs the general path's own call and
unboxes the result with a check of the exact tag: a stub is a claim about CPython, not about
AIL's own code, so a value of another tag stops the program by name.  A lowered helper whose
typed clone already returns the scalar skips the check.

`AIL_STUBCALLS=0` turns the feature off.
"""
import ast
import os

import stubsigs


def _enabled():
    return os.environ.get('AIL_STUBCALLS', '').strip().lower() not in ('0', 'off', 'no', 'false')


def _bindings(tree):
    """Names the program binds outside an import (a scope-insensitive over-approximation)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if not isinstance(node, ast.ClassDef):
                args = node.args
                for arg in (list(getattr(args, 'posonlyargs', [])) + list(args.args)
                            + list(args.kwonlyargs)):
                    names.add(arg.arg)
                if args.vararg is not None:
                    names.add(args.vararg.arg)
                if args.kwarg is not None:
                    names.add(args.kwarg.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
    return names


def _imports(plan):
    """local name -> real qualname prefix (`m` in `import math as m` -> `math`)."""
    got = getattr(plan, '_stub_imports', None)
    if got is not None:
        return got
    tree = getattr(plan, '_tree', None)
    found = {}
    if tree is not None:
        rebound = _bindings(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split('.')[0]
                    if local not in rebound:
                        found[local] = alias.name if alias.asname else alias.name.split('.')[0]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                for alias in node.names:
                    if alias.name == '*':
                        continue
                    local = alias.asname or alias.name
                    if local not in rebound:
                        found[local] = node.module + '.' + alias.name
        # the Python surface treats a few stdlib functions as builtins and drops their import line
        try:
            import pyboxed2
            for name, module in pyboxed2._IMPLICIT_LIB.items():
                if name not in rebound:
                    found.setdefault(name, module + '.' + name)
        except Exception:
            pass
    plan._stub_imports = found
    return found


def qualname(plan, fp, node):
    """The vendored qualname of `node.func`, or None when it is not an imported stdlib callee."""
    if not isinstance(node, ast.Call):
        return None
    imports = _imports(plan)
    func = node.func
    chain = []
    while isinstance(func, ast.Attribute):
        chain.append(func.attr)
        func = func.value
    if not isinstance(func, ast.Name):
        return None
    base = func.id
    if fp is not None and base in fp.locals:
        return None
    if not chain and base.startswith('_ail_math_'):
        return 'math.' + base[len('_ail_math_'):]      # the Python surface lowers math.f(...) to this helper
    if base in plan.fn_names:
        return None
    target = imports.get(base)
    if target is None:
        return None
    return '.'.join([target] + list(reversed(chain)))


def call_type(plan, fp, node, env):
    """The checked scalar type of `node`, or None (the caller keeps the boxed `obj`)."""
    if not _enabled():
        return None
    name = qualname(plan, fp, node)
    if name is None:
        return None
    if name in stubsigs.DENY:
        return None
    if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
        return None
    entry = stubsigs.lookup(name)
    if entry is None:
        return None
    ret, _params, flags = entry
    if flags or ret not in ('int', 'float', 'bool'):
        return None
    if ret == 'int':
        if fp is None or fp.exact:
            return None                     # an exact function keeps big ints boxed
    return ret


def unbox_checked(comp, ctx, node, t):
    """Emit the general path's call, then unbox it after checking the exact tag."""
    import unified
    name = qualname(comp.uplan, getattr(ctx, 'u', None), node) or '?'
    s = ctx.tmp()
    spec = getattr(comp.uplan, 'spec', {})
    f = node.func.id if isinstance(node.func, ast.Name) else None
    if f in spec and spec[f].ret == t:
        # the compiler's own typed clone already returns this scalar: no tag check is needed
        v, _ = unified.call_spec(comp, f, node.args, ctx)
        ctx.emit('/* AIL stub call %s: typed clone */' % name)
        return v
    if f in spec and spec[f].ret not in (unified.INT, unified.FLOAT, unified.BOOL):
        # the lowered helper has a typed clone (`pfu_`) for its parameters but a boxed return: call
        # that clone with native arguments instead of going back through the all-boxed body
        boxed, _ = unified.call_spec(comp, f, node.args, ctx)
    else:
        boxed = comp._expr_plain(node, ctx)
    ctx.emit('%s = %s;' % (s, boxed))
    if t == unified.INT:
        ctx.emit('if ((%s).tag != AIL_T_INT) {\n'
                 '            ail_out_flush(cx);\n'
                 '            fputs("AIL stub call %s: stub says int\\n", stderr);\n'
                 '            fflush(stderr); _Exit(2);\n'
                 '        }' % (s, name))
        unified._big_stop(ctx, s)
        r = unified.utmp(ctx, unified.INT)
        ctx.emit('%s = (%s).i;' % (r, s))
        return r
    if t == unified.FLOAT:
        ctx.emit('if ((%s).tag != AIL_T_FLOAT) {\n'
                 '            ail_out_flush(cx);\n'
                 '            fputs("AIL stub call %s: stub says float\\n", stderr);\n'
                 '            fflush(stderr); _Exit(2);\n'
                 '        }' % (s, name))
        r = unified.utmp(ctx, unified.FLOAT)
        ctx.emit('%s = ail_float_val(%s);' % (r, s))
        return r
    ctx.emit('if ((%s).tag != AIL_T_BOOL) {\n'
             '            ail_out_flush(cx);\n'
             '            fputs("AIL stub call %s: stub says bool\\n", stderr);\n'
             '            fflush(stderr); _Exit(2);\n'
             '        }' % (s, name))
    r = unified.utmp(ctx, unified.BOOL)
    ctx.emit('%s = ((%s).i != 0);' % (r, s))
    return r
