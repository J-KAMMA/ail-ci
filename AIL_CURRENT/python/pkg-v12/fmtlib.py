# -*- coding: utf-8 -*-
"""str.format / str.format_map on the general (boxed) path (called from pyboxed2.Compiler.compile, general path only).

The general path's own `.format` needs a library table this tree does not carry, so every `.format(...)` was refused
(and `.format(k=v)` by name). `rewrite(tree)` turns

    S.format(a, b, k=v, *more, **kw)     ->   _ail_str_format(S, [a, b, *more], {"k": v, **kw})
    S.format_map(m)                      ->   _ail_str_format(S, [], m)

and adds prelude_format.py (a port of CPython's unicode_format.h: nested replacement fields in the spec, `{0[1]}`,
`{p.x}`, `!r` `!s` `!a`, the numbering rules and the error texts). The typed path is not touched (it never sees this).

A receiver that is not a str literal is rewritten only when the program has no def or method called `format` /
`format_map` of its own (then every `.format` is the str method); with one, only literal templates are, and a call on a
value of another kind is left as written.
"""
import ast
import os

import stdlib5

HERE = os.path.dirname(os.path.abspath(__file__))


def is_str_literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def rewrite(tree):
    """Rewrite the .format calls of `tree` in place; returns the prelude source or ''."""
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in ('format', 'format_map')]
    if not calls:
        return ''
    own = any(isinstance(n, ast.FunctionDef) and n.name in ('format', 'format_map') for n in ast.walk(tree))
    modules = set()
    for n in tree.body:
        if isinstance(n, ast.Import):
            modules.update((a.asname or a.name).split('.')[0] for a in n.names)
    used = [False]
    roots = {'_ail_str_format'}

    def fix(node):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ('format', 'format_map')):
            return None
        recv = node.func.value
        if isinstance(recv, ast.Name) and recv.id in modules:
            return None
        if own and not is_str_literal(recv):
            return None
        if node.func.attr == 'format_map':
            if len(node.args) != 1 or node.keywords or isinstance(node.args[0], ast.Starred):
                return None
            args = ast.List(elts=[], ctx=ast.Load())
            kwargs = node.args[0]
        else:
            args = ast.List(elts=[stdlib5.Replace(fix).visit(a) for a in node.args], ctx=ast.Load())
            keys, values = [], []
            for kw in node.keywords:
                keys.append(None if kw.arg is None else ast.Constant(value=kw.arg))
                values.append(stdlib5.Replace(fix).visit(kw.value))
            if len(keys) == 1 and keys[0] is None:
                kwargs = values[0]
            elif None in keys:
                # a ** unpacking among the keywords (not built inside a dict display): merged by a helper
                named = ast.Dict(keys=[k for k in keys if k is not None],
                                 values=[v for k, v in zip(keys, values) if k is not None])
                kwargs = ast.Call(func=ast.Name(id='_ail_fmt_merge', ctx=ast.Load()),
                                  args=[named] + [v for k, v in zip(keys, values) if k is None], keywords=[])
                roots.add('_ail_fmt_merge')
            else:
                kwargs = ast.Dict(keys=keys, values=values)
        used[0] = True
        return ast.Call(func=ast.Name(id='_ail_str_format', ctx=ast.Load()),
                        args=[stdlib5.Replace(fix).visit(recv), args, kwargs], keywords=[])
    tree.body = [stdlib5.Replace(fix).visit(s) for s in tree.body]
    if not used[0]:
        return ''
    ast.fix_missing_locations(tree)
    return stdlib5.shake(open(os.path.join(HERE, 'prelude_format.py'), encoding='utf-8').read(), roots)
