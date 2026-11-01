"""`cmath` over a small complex class (library batch 5, called from stdlib5).

The language has no complex type, so `import cmath` lowers the module's calls and constants onto the
Python source of prelude_cmath.py: a class with the arithmetic operators, the same numerical
algorithms as CPython 3.12's Modules/cmathmodule.c / Objects/complexobject.c, and CPython's complex
repr. Complex literals (`1j`, `2+3j`) and `complex(...)` are lowered with the module; `isinstance(x,
complex)` reads the class. A program that imports none of them is returned as written, so its C does
not change.
"""
import ast
import math

import stdlib5

FUNCTIONS = {
    'acos': '_ail_cm_acos',
    'acosh': '_ail_cm_acosh',
    'asin': '_ail_cm_asin',
    'asinh': '_ail_cm_asinh',
    'atan': '_ail_cm_atan',
    'atanh': '_ail_cm_atanh',
    'cos': '_ail_cm_cos',
    'cosh': '_ail_cm_cosh',
    'exp': '_ail_cm_exp',
    'isclose': '_ail_cm_isclose',
    'isfinite': '_ail_cm_isfinite',
    'isinf': '_ail_cm_isinf',
    'isnan': '_ail_cm_isnan',
    'log': '_ail_cm_log',
    'log10': '_ail_cm_log10',
    'phase': '_ail_cm_phase',
    'polar': '_ail_cm_polar',
    'rect': '_ail_cm_rect',
    'sin': '_ail_cm_sin',
    'sinh': '_ail_cm_sinh',
    'sqrt': '_ail_cm_sqrt',
    'tan': '_ail_cm_tan',
    'tanh': '_ail_cm_tanh',
}

CONSTANTS = ('pi', 'e', 'tau', 'inf', 'nan', 'infj', 'nanj')

HANDLED = frozenset(FUNCTIONS) | frozenset(CONSTANTS)

WHAT = ('acos, acosh, asin, asinh, atan, atanh, cos, cosh, exp, isclose, isfinite, isinf, isnan, '
        'log, log10, phase, polar, rect, sin, sinh, sqrt, tan, tanh, pi, e, tau, inf, nan, infj '
        'and nanj are built')


def _name(identifier):
    return ast.Name(id=identifier, ctx=ast.Load())


def _call(func, args, keywords=None):
    return ast.Call(func=_name(func), args=list(args), keywords=list(keywords or []))


def _raise(message, values):
    return _call('_ail_cm_raise', [ast.Constant(value=message)] + list(values))


def _float(value):
    return ast.Constant(value=float(value))


def _complex_literal(value):
    return _call('_AilComplex', [_float(value.real), _float(value.imag)])


def _const(name):
    if name == 'pi':
        return ast.Constant(value=math.pi)
    if name == 'e':
        return ast.Constant(value=math.e)
    if name == 'tau':
        return ast.Constant(value=math.tau)
    if name == 'inf':
        return _name('_AIL_CM_INF')
    if name == 'nan':
        return _name('_AIL_CM_NAN')
    if name == 'infj':
        return _call('_AilComplex', [_float(0.0), _name('_AIL_CM_INF')])
    return _call('_AilComplex', [_float(0.0), _name('_AIL_CM_NAN')])


def _bound_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
            names.add(node.id)
    return names


def _complex_call(node):
    """`complex(...)` written the CPython way, as one of the prelude constructors; None when the
    call has a shape the constructors do not take (the compiler then reports it)."""
    keywords = [k for k in node.keywords if k.arg is not None]
    if len(keywords) != len(node.keywords):
        return None
    args = list(node.args)
    kw = {k.arg: k.value for k in keywords}
    if any(name not in ('real', 'imag') for name in kw) or len(kw) != len(keywords):
        return None
    if len(args) > 2:
        return None
    if len(args) == 2:
        if 'real' in kw or 'imag' in kw:
            return None
        return _call('_ail_cm_from_two', args)
    if len(args) == 1:
        if 'real' in kw:
            return None
        if 'imag' in kw:
            return _call('_ail_cm_from_two', [args[0], kw['imag']])
        return _call('_ail_cm_from_one', args)
    if 'imag' not in kw and 'real' in kw:
        return _call('_ail_cm_from_one', [kw['real']])
    if 'real' in kw or 'imag' in kw:
        return _call('_ail_cm_from_two', [kw.get('real', _float(0.0)), kw.get('imag', _float(0.0))])
    return _call('_ail_cm_from_two', [_float(0.0), _float(0.0)])


def rewrite(tree, text):
    binder = stdlib5.take_imports(tree, 'cmath', HANDLED, unknown=WHAT)
    if not binder:
        return
    shadowed = _bound_names(tree)
    user_complex = 'complex' in shadowed

    def fix(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, complex):
            return _complex_literal(node.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'complex' \
                and not user_complex:
            lowered = _complex_call(node)
            if lowered is not None:
                return stdlib5.Replace(fix).visit(lowered)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'isinstance' \
                and len(node.args) == 2 and isinstance(node.args[1], ast.Name) and node.args[1].id == 'complex' \
                and not user_complex:
            node.args[1] = _name('_AilComplex')
            return stdlib5.Replace(fix).visit(node)
        if isinstance(node, ast.Call) and not any(isinstance(a, ast.Starred) for a in node.args):
            found = binder.attr(node.func)
            if found in FUNCTIONS:
                values = list(node.args) + [k.value for k in node.keywords]
                if found == 'isclose':
                    if len(node.args) > 2:
                        lowered = _raise('isclose() takes exactly 2 positional arguments (%d given)'
                                         % len(node.args), values)
                        return stdlib5.Replace(fix).visit(lowered)
                    for k in node.keywords:
                        if k.arg not in ('a', 'b', 'rel_tol', 'abs_tol'):
                            lowered = _raise("'%s' is an invalid keyword argument for isclose()" % k.arg,
                                             values)
                            return stdlib5.Replace(fix).visit(lowered)
                elif node.keywords:
                    lowered = _raise('cmath.%s() takes no keyword arguments' % found, values)
                    return stdlib5.Replace(fix).visit(lowered)
        found = binder.attr(node)
        if found in FUNCTIONS:
            return _name(FUNCTIONS[found])
        if found in CONSTANTS:
            return _const(found)
        return None

    tree.body = [stdlib5.Replace(fix).visit(stmt) for stmt in tree.body]
    binder.names.clear()
    stdlib5.leftover(tree, binder, WHAT)
    text.append(stdlib5.prelude('cmath'))
