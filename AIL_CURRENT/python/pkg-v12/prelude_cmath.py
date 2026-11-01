# -*- coding: utf-8 -*-
# prelude_cmath.py -- `cmath` over a complex class (library batch 5, cmathlib.py injects it).
#
# Plain Python in the subset the general path builds, and a module CPython can import as it
# stands (the tests compare the pieces with the real cmath). The algorithms are CPython 3.12's
# Modules/cmathmodule.c and Objects/complexobject.c; the special-value tables are theirs too.
import math

def _ail_cm_make_inf() -> float:
    x = 1e308
    return x * 10.0


def _ail_cm_make_nan() -> float:
    x = _AIL_CM_INF
    return x - x


_AIL_CM_INF = _ail_cm_make_inf()
_AIL_CM_NAN = _ail_cm_make_nan()
_AIL_CM_U = -9.5426319407711027e33
_AIL_CM_LARGE = 1.7976931348623157e308 / 4.0
_AIL_CM_SQRT_LARGE = math.sqrt(_AIL_CM_LARGE)
_AIL_CM_LOG_LARGE = math.log(_AIL_CM_LARGE)
_AIL_CM_SQRT_DBL_MIN = math.sqrt(2.2250738585072014e-308)
_AIL_CM_SCALE_UP = 53
_AIL_CM_SCALE_DOWN = -27
_AIL_CM_LN2 = 0.6931471805599453094
_AIL_CM_LN10 = 2.302585092994045684

_AIL_CM_ACOS_SPECIAL = [
    2.356194490192345, _AIL_CM_INF, 3.141592653589793, _AIL_CM_INF, 3.141592653589793, _AIL_CM_INF, 3.141592653589793, -_AIL_CM_INF,
    3.141592653589793, -_AIL_CM_INF, 2.356194490192345, -_AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, 1.5707963267948966, _AIL_CM_INF,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    1.5707963267948966, -_AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, 1.5707963267948966, _AIL_CM_INF, -9.542631940771103e+33, -9.542631940771103e+33,
    1.5707963267948966, 0.0, 1.5707963267948966, -0.0, -9.542631940771103e+33, -9.542631940771103e+33, 1.5707963267948966, -_AIL_CM_INF,
    1.5707963267948966, _AIL_CM_NAN, 1.5707963267948966, _AIL_CM_INF, -9.542631940771103e+33, -9.542631940771103e+33, 1.5707963267948966, 0.0,
    1.5707963267948966, -0.0, -9.542631940771103e+33, -9.542631940771103e+33, 1.5707963267948966, -_AIL_CM_INF, 1.5707963267948966, _AIL_CM_NAN,
    1.5707963267948966, _AIL_CM_INF, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, 1.5707963267948966, -_AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, 0.7853981633974483, _AIL_CM_INF,
    0.0, _AIL_CM_INF, 0.0, _AIL_CM_INF, 0.0, -_AIL_CM_INF, 0.0, -_AIL_CM_INF,
    0.7853981633974483, -_AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, -_AIL_CM_INF,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

_AIL_CM_ACOSH_SPECIAL = [
    _AIL_CM_INF, -2.356194490192345, _AIL_CM_INF, -3.141592653589793, _AIL_CM_INF, -3.141592653589793, _AIL_CM_INF, 3.141592653589793,
    _AIL_CM_INF, 3.141592653589793, _AIL_CM_INF, 2.356194490192345, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, -1.5707963267948966,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_INF, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33,
    0.0, -1.5707963267948966, 0.0, 1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, 1.5707963267948966,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, -1.5707963267948966,
    0.0, 1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_INF, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -0.7853981633974483,
    _AIL_CM_INF, -0.0, _AIL_CM_INF, -0.0, _AIL_CM_INF, 0.0, _AIL_CM_INF, 0.0,
    _AIL_CM_INF, 0.7853981633974483, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

_AIL_CM_ASINH_SPECIAL = [
    -_AIL_CM_INF, -0.7853981633974483, -_AIL_CM_INF, -0.0, -_AIL_CM_INF, -0.0, -_AIL_CM_INF, 0.0,
    -_AIL_CM_INF, 0.0, -_AIL_CM_INF, 0.7853981633974483, -_AIL_CM_INF, _AIL_CM_NAN, -_AIL_CM_INF, -1.5707963267948966,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -_AIL_CM_INF, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN, -_AIL_CM_INF, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33,
    -0.0, -0.0, -0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, -_AIL_CM_INF, 1.5707963267948966,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, -0.0,
    0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_INF, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -0.7853981633974483,
    _AIL_CM_INF, -0.0, _AIL_CM_INF, -0.0, _AIL_CM_INF, 0.0, _AIL_CM_INF, 0.0,
    _AIL_CM_INF, 0.7853981633974483, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, -0.0, _AIL_CM_NAN, 0.0, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

_AIL_CM_ATANH_SPECIAL = [
    -0.0, -1.5707963267948966, -0.0, -1.5707963267948966, -0.0, -1.5707963267948966, -0.0, 1.5707963267948966,
    -0.0, 1.5707963267948966, -0.0, 1.5707963267948966, -0.0, _AIL_CM_NAN, -0.0, -1.5707963267948966,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -0.0, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN, -0.0, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33,
    -0.0, -0.0, -0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, -0.0, 1.5707963267948966,
    -0.0, _AIL_CM_NAN, 0.0, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, -0.0,
    0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, 1.5707963267948966, 0.0, _AIL_CM_NAN,
    0.0, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, 0.0, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN, 0.0, -1.5707963267948966,
    0.0, -1.5707963267948966, 0.0, -1.5707963267948966, 0.0, 1.5707963267948966, 0.0, 1.5707963267948966,
    0.0, 1.5707963267948966, 0.0, _AIL_CM_NAN, 0.0, -1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, 0.0, 1.5707963267948966,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

_AIL_CM_COSH_SPECIAL = [
    _AIL_CM_INF, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, 0.0, _AIL_CM_INF, -0.0,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, 0.0, -9.542631940771103e+33, -9.542631940771103e+33,
    1.0, 0.0, 1.0, -0.0, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, 0.0,
    _AIL_CM_NAN, 0.0, _AIL_CM_NAN, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, 1.0, -0.0,
    1.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, 0.0, _AIL_CM_NAN, 0.0,
    _AIL_CM_NAN, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, -0.0, _AIL_CM_INF, 0.0, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, 0.0, _AIL_CM_NAN, 0.0, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

_AIL_CM_EXP_SPECIAL = [
    0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, -0.0, 0.0, 0.0,
    -9.542631940771103e+33, -9.542631940771103e+33, 0.0, 0.0, 0.0, 0.0, _AIL_CM_NAN, _AIL_CM_NAN,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33,
    1.0, -0.0, 1.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, 1.0, -0.0,
    1.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, -0.0, _AIL_CM_INF, 0.0, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, -0.0, _AIL_CM_NAN, 0.0, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

_AIL_CM_LOG_SPECIAL = [
    _AIL_CM_INF, -2.356194490192345, _AIL_CM_INF, -3.141592653589793, _AIL_CM_INF, -3.141592653589793, _AIL_CM_INF, 3.141592653589793,
    _AIL_CM_INF, 3.141592653589793, _AIL_CM_INF, 2.356194490192345, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, -1.5707963267948966,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_INF, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33,
    -_AIL_CM_INF, -3.141592653589793, -_AIL_CM_INF, 3.141592653589793, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, 1.5707963267948966,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33, -_AIL_CM_INF, -0.0,
    -_AIL_CM_INF, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_INF, -1.5707963267948966, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, 1.5707963267948966, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -0.7853981633974483,
    _AIL_CM_INF, -0.0, _AIL_CM_INF, -0.0, _AIL_CM_INF, 0.0, _AIL_CM_INF, 0.0,
    _AIL_CM_INF, 0.7853981633974483, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

_AIL_CM_SINH_SPECIAL = [
    _AIL_CM_INF, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, -_AIL_CM_INF, -0.0, -_AIL_CM_INF, 0.0,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, 0.0, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33,
    -0.0, -0.0, -0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, _AIL_CM_NAN,
    0.0, _AIL_CM_NAN, 0.0, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, -0.0,
    0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, _AIL_CM_NAN, 0.0, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, -0.0, _AIL_CM_INF, 0.0, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, -0.0, _AIL_CM_NAN, 0.0, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

_AIL_CM_SQRT_SPECIAL = [
    _AIL_CM_INF, -_AIL_CM_INF, 0.0, -_AIL_CM_INF, 0.0, -_AIL_CM_INF, 0.0, _AIL_CM_INF,
    0.0, _AIL_CM_INF, _AIL_CM_INF, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_INF, -_AIL_CM_INF,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_INF, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -_AIL_CM_INF, -9.542631940771103e+33, -9.542631940771103e+33,
    0.0, -0.0, 0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, _AIL_CM_INF,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -_AIL_CM_INF, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, -0.0,
    0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_INF, -_AIL_CM_INF, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, -_AIL_CM_INF,
    _AIL_CM_INF, -0.0, _AIL_CM_INF, -0.0, _AIL_CM_INF, 0.0, _AIL_CM_INF, 0.0,
    _AIL_CM_INF, _AIL_CM_INF, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, -_AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_INF,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

_AIL_CM_TANH_SPECIAL = [
    -1.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, -1.0, -0.0, -1.0, 0.0,
    -9.542631940771103e+33, -9.542631940771103e+33, -1.0, 0.0, -1.0, 0.0, _AIL_CM_NAN, _AIL_CM_NAN,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33,
    -0.0, -0.0, -0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, -0.0,
    0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, 1.0, 0.0,
    -9.542631940771103e+33, -9.542631940771103e+33, 1.0, -0.0, 1.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33,
    1.0, 0.0, 1.0, 0.0, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, -0.0, _AIL_CM_NAN, 0.0, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

_AIL_CM_RECT_SPECIAL = [
    _AIL_CM_INF, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, -_AIL_CM_INF, 0.0, -_AIL_CM_INF, -0.0,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, 0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33,
    -0.0, 0.0, -0.0, -0.0, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, -0.0,
    0.0, 0.0, -9.542631940771103e+33, -9.542631940771103e+33, 0.0, 0.0, 0.0, 0.0,
    _AIL_CM_NAN, _AIL_CM_NAN, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33, -9.542631940771103e+33,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN,
    -9.542631940771103e+33, -9.542631940771103e+33, _AIL_CM_INF, -0.0, _AIL_CM_INF, 0.0, -9.542631940771103e+33, -9.542631940771103e+33,
    _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_INF, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, 0.0, _AIL_CM_NAN, 0.0, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN, _AIL_CM_NAN,
    _AIL_CM_NAN, _AIL_CM_NAN,
]

def _ail_cm_frepr(x: float) -> str:
    s = repr(x)
    if s.endswith(".0"):
        return s[:-2]
    return s


def _ail_cm_typ(d: float) -> int:
    if math.isfinite(d):
        if d != 0.0:
            if math.copysign(1.0, d) > 0.0:
                return 4
            return 1
        if math.copysign(1.0, d) > 0.0:
            return 3
        return 2
    if math.isnan(d):
        return 6
    if math.copysign(1.0, d) > 0.0:
        return 5
    return 0


def _ail_cm_special(table, z):
    if not math.isfinite(z.real) or not math.isfinite(z.imag):
        i = 2 * (_ail_cm_typ(z.real) * 7 + _ail_cm_typ(z.imag))
        return _AilComplex(table[i], table[i + 1])
    return None


class _AilComplex:
    def __init__(self, real: float, imag: float) -> None:
        self.real = real
        self.imag = imag

    def __repr__(self) -> str:
        if self.real == 0.0 and math.copysign(1.0, self.real) > 0.0:
            return _ail_cm_frepr(self.imag) + "j"
        im = _ail_cm_frepr(self.imag)
        if not im.startswith("-"):
            im = "+" + im
        return "(" + _ail_cm_frepr(self.real) + im + "j)"

    def __str__(self) -> str:
        return self.__repr__()

    def conjugate(self):
        return _AilComplex(self.real, -self.imag)

    def __bool__(self) -> bool:
        return self.real != 0.0 or self.imag != 0.0

    def __neg__(self):
        return _AilComplex(-self.real, -self.imag)

    def __pos__(self):
        return _AilComplex(self.real, self.imag)

    def __abs__(self) -> float:
        return _ail_cm_abs(self)

    def __add__(self, other):
        b = _ail_cm_as(other)
        return _AilComplex(self.real + b.real, self.imag + b.imag)

    def __radd__(self, other):
        return _ail_cm_as(other).__add__(self)

    def __sub__(self, other):
        b = _ail_cm_as(other)
        return _AilComplex(self.real - b.real, self.imag - b.imag)

    def __rsub__(self, other):
        return _ail_cm_as(other).__sub__(self)

    def __mul__(self, other):
        b = _ail_cm_as(other)
        return _AilComplex(self.real * b.real - self.imag * b.imag,
                           self.real * b.imag + self.imag * b.real)

    def __rmul__(self, other):
        return _ail_cm_as(other).__mul__(self)

    def __truediv__(self, other):
        return _ail_cm_div(self, _ail_cm_as(other))

    def __rtruediv__(self, other):
        return _ail_cm_div(_ail_cm_as(other), self)

    def __pow__(self, other):
        b = _ail_cm_as(other)
        if b.imag == 0.0 and math.isfinite(b.real) and b.real == math.floor(b.real) \
                and abs(b.real) <= 100.0 \
                and (self.real != 0.0 or self.imag != 0.0 or b.real >= 0.0):
            r = _ail_cm_powi(self, int(b.real))
            if math.isinf(r.real) or math.isinf(r.imag):
                raise OverflowError("complex exponentiation")
            return r
        return _ail_cm_cpow(self, b)

    def __rpow__(self, other):
        return _ail_cm_as(other).__pow__(self)

    def __eq__(self, other):
        if isinstance(other, _AilComplex):
            return self.real == other.real and self.imag == other.imag
        if isinstance(other, bool) or isinstance(other, int) or isinstance(other, float):
            return self.real == other and self.imag == 0.0
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return _ail_cm_hash(self.real, self.imag)


def _ail_cm_tname(x) -> str:
    if x is None:
        return "NoneType"
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "str"
    if isinstance(x, _AilComplex):
        return "complex"
    if isinstance(x, list):
        return "list"
    if isinstance(x, tuple):
        return "tuple"
    if isinstance(x, dict):
        return "dict"
    return "object"


def _ail_cm_raise(message: str, *values) -> None:
    raise TypeError(message)


class _AilCMKeyword:
    def __init__(self, key: str, value) -> None:
        self.key = key
        self.value = value


class _AilCMStarred:
    def __init__(self, value) -> None:
        self.value = value


def _ail_cm_kwarg(key: str, value):
    return _AilCMKeyword(key, value)


def _ail_cm_star(value):
    return _AilCMStarred(value)


def _ail_cm_args(*parts):
    out = []
    for part in parts:
        if isinstance(part, _AilCMStarred):
            for item in part.value:
                out.append(item)
        else:
            out.append(part)
    return tuple(out)


def _ail_cm_kw(name: str, args, *parts):
    kw = {}
    for part in parts:
        if isinstance(part, _AilCMKeyword):
            key = part.key
            if key in kw:
                raise TypeError("cmath.%s() got multiple values for keyword argument '%s'" % (name, key))
            kw[key] = part.value
            continue
        if isinstance(part, dict):
            keys = list(part.keys())
        else:
            try:
                keys = list(part.keys())
            except AttributeError:
                raise TypeError("cmath.%s() argument after ** must be a mapping, not %s"
                                % (name, _ail_cm_tname(part)))
        for key in keys:
            if not isinstance(key, str):
                raise TypeError("keywords must be strings")
            if key in kw:
                raise TypeError("cmath.%s() got multiple values for keyword argument '%s'" % (name, key))
            kw[key] = part[key]
    if name == 'isclose':
        return _ail_cm_kw_isclose(args, kw)
    if name == 'log':
        return _ail_cm_kw_log(args, kw)
    if name == 'rect':
        return _ail_cm_kw_rect(args, kw)
    return _ail_cm_kw_one(name, args, kw)


def _ail_cm_kw_one(name: str, args, kw):
    if kw:
        raise TypeError("cmath.%s() takes no keyword arguments" % name)
    if len(args) != 1:
        raise TypeError("cmath.%s() takes exactly one argument (%d given)" % (name, len(args)))
    z = args[0]
    if name == 'acos':
        return _ail_cm_acos(z)
    if name == 'acosh':
        return _ail_cm_acosh(z)
    if name == 'asin':
        return _ail_cm_asin(z)
    if name == 'asinh':
        return _ail_cm_asinh(z)
    if name == 'atan':
        return _ail_cm_atan(z)
    if name == 'atanh':
        return _ail_cm_atanh(z)
    if name == 'cos':
        return _ail_cm_cos(z)
    if name == 'cosh':
        return _ail_cm_cosh(z)
    if name == 'exp':
        return _ail_cm_exp(z)
    if name == 'isfinite':
        return _ail_cm_isfinite(z)
    if name == 'isinf':
        return _ail_cm_isinf(z)
    if name == 'isnan':
        return _ail_cm_isnan(z)
    if name == 'log10':
        return _ail_cm_log10(z)
    if name == 'phase':
        return _ail_cm_phase(z)
    if name == 'polar':
        return _ail_cm_polar(z)
    if name == 'sin':
        return _ail_cm_sin(z)
    if name == 'sinh':
        return _ail_cm_sinh(z)
    if name == 'sqrt':
        return _ail_cm_sqrt(z)
    if name == 'tan':
        return _ail_cm_tan(z)
    return _ail_cm_tanh(z)


def _ail_cm_kw_log(args, kw):
    if kw:
        raise TypeError("cmath.log() takes no keyword arguments")
    if len(args) < 1:
        raise TypeError("log expected at least 1 argument, got 0")
    if len(args) > 2:
        raise TypeError("log expected at most 2 arguments, got %d" % len(args))
    if len(args) == 2:
        return _ail_cm_log(args[0], args[1])
    return _ail_cm_log(args[0])


def _ail_cm_kw_rect(args, kw):
    if kw:
        raise TypeError("cmath.rect() takes no keyword arguments")
    if len(args) != 2:
        raise TypeError("rect expected 2 arguments, got %d" % len(args))
    return _ail_cm_rect(args[0], args[1])


def _ail_cm_kw_isclose(args, kw):
    if len(args) > 2:
        raise TypeError("isclose() takes exactly 2 positional arguments (%d given)" % len(args))
    if len(args) >= 1:
        if 'a' in kw:
            raise TypeError("argument for isclose() given by name ('a') and position (1)")
        a = args[0]
    elif 'a' in kw:
        a = kw['a']
    else:
        raise TypeError("isclose() missing required argument 'a' (pos 1)")
    if len(args) >= 2:
        if 'b' in kw:
            raise TypeError("argument for isclose() given by name ('b') and position (2)")
        b = args[1]
    elif 'b' in kw:
        b = kw['b']
    else:
        raise TypeError("isclose() missing required argument 'b' (pos 2)")
    for key in kw:
        if key not in ('a', 'b', 'rel_tol', 'abs_tol'):
            raise TypeError("'%s' is an invalid keyword argument for isclose()" % key)
    rel_tol = 1e-09
    abs_tol = 0.0
    if 'rel_tol' in kw:
        rel_tol = kw['rel_tol']
    if 'abs_tol' in kw:
        abs_tol = kw['abs_tol']
    return _ail_cm_isclose(a, b, rel_tol, abs_tol)


def _ail_cm_arg(x):
    if isinstance(x, _AilComplex):
        return x
    if isinstance(x, bool) or isinstance(x, int) or isinstance(x, float):
        return _AilComplex(float(x), 0.0)
    raise TypeError("must be real number, not %s" % _ail_cm_tname(x))


def _ail_cm_float_arg(x) -> float:
    if isinstance(x, bool) or isinstance(x, int) or isinstance(x, float):
        return float(x)
    raise TypeError("must be real number, not %s" % _ail_cm_tname(x))


def _ail_cm_hash(real: float, imag: float) -> int:
    hreal = hash(real)
    himag = hash(imag)
    lo = himag & 0xFFFFFFFF
    hi = (himag >> 32) & 0xFFFFFFFF
    prod = lo * 1000003
    plo = prod & 0xFFFFFFFF
    phi = ((prod >> 32) + hi * 1000003) & 0xFFFFFFFF
    alo = hreal & 0xFFFFFFFF
    ahi = (hreal >> 32) & 0xFFFFFFFF
    slo = plo + alo
    carry = slo >> 32
    slo = slo & 0xFFFFFFFF
    shi = (phi + ahi + carry) & 0xFFFFFFFF
    if shi >= 0x80000000:
        combined = (shi - 0x100000000) * 4294967296 + slo
    else:
        combined = shi * 4294967296 + slo
    if combined == -1:
        return -2
    return combined


def _ail_cm_real(x) -> float:
    if isinstance(x, _AilComplex):
        return x.real
    if isinstance(x, bool) or isinstance(x, int) or isinstance(x, float):
        return float(x)
    raise TypeError("complex() argument must be a string or a number, not '%s'" % _ail_cm_tname(x))


def _ail_cm_as(x):
    if isinstance(x, _AilComplex):
        return x
    return _AilComplex(_ail_cm_real(x), 0.0)


def _ail_cm_strfloat(s: str) -> float:
    try:
        return float(s)
    except ValueError:
        raise ValueError("complex() arg is a malformed string")


def _ail_cm_parse(s: str):
    t = s.strip()
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1].strip()
    if t == "":
        raise ValueError("complex() arg is a malformed string")
    for ch in t:
        if ch.isspace():
            raise ValueError("complex() arg is a malformed string")
    if t.endswith("j"):
        body = t[:-1]
        pos = -1
        i = 0
        while i < len(body):
            if body[i] in "+-" and i > 0 and body[i - 1] not in "eE":
                pos = i
            i = i + 1
        if pos < 0:
            re = 0.0
            im = 1.0 if body == "" or body == "+" else (-1.0 if body == "-" else _ail_cm_strfloat(body))
            return _AilComplex(re, im)
        re = _ail_cm_strfloat(body[:pos])
        tail = body[pos:]
        im = 1.0 if tail == "+" else (-1.0 if tail == "-" else _ail_cm_strfloat(tail))
        return _AilComplex(re, im)
    return _AilComplex(_ail_cm_strfloat(t), 0.0)


def _ail_cm_from_one(x):
    if isinstance(x, _AilComplex):
        return _AilComplex(x.real, x.imag)
    if isinstance(x, str):
        return _ail_cm_parse(x)
    if isinstance(x, bool) or isinstance(x, int) or isinstance(x, float):
        return _AilComplex(float(x), 0.0)
    raise TypeError("complex() first argument must be a string or a number, not '%s'"
                    % _ail_cm_tname(x))


def _ail_cm_from_two(real, imag):
    if isinstance(real, str):
        raise TypeError("complex() can't take second arg if first is a string")
    if isinstance(imag, str):
        raise TypeError("complex() second arg can't be a string")
    if not (isinstance(real, _AilComplex) or isinstance(real, bool)
            or isinstance(real, int) or isinstance(real, float)):
        raise TypeError("complex() first argument must be a string or a number, not '%s'"
                        % _ail_cm_tname(real))
    if not (isinstance(imag, _AilComplex) or isinstance(imag, bool)
            or isinstance(imag, int) or isinstance(imag, float)):
        raise TypeError("complex() second argument must be a number, not '%s'"
                        % _ail_cm_tname(imag))
    if isinstance(real, _AilComplex):
        if isinstance(imag, _AilComplex):
            return _AilComplex(real.real - imag.imag, real.imag + imag.real)
        return _AilComplex(real.real, real.imag + _ail_cm_real(imag))
    if isinstance(imag, _AilComplex):
        return _AilComplex(_ail_cm_real(real) - imag.imag, imag.real)
    return _AilComplex(_ail_cm_real(real), _ail_cm_real(imag))


def _ail_cm_abs(z) -> float:
    if not math.isfinite(z.real) or not math.isfinite(z.imag):
        if math.isinf(z.real):
            return abs(z.real)
        if math.isinf(z.imag):
            return abs(z.imag)
        return _AIL_CM_NAN
    return math.hypot(z.real, z.imag)


def _ail_cm_div(a, b):
    abs_breal = abs(b.real)
    abs_bimag = abs(b.imag)
    if abs_breal >= abs_bimag:
        if abs_breal == 0.0:
            raise ZeroDivisionError("complex division by zero")
        ratio = b.imag / b.real
        denom = b.real + b.imag * ratio
        return _AilComplex((a.real + a.imag * ratio) / denom,
                           (a.imag - a.real * ratio) / denom)
    if abs_bimag >= abs_breal:
        ratio = b.real / b.imag
        denom = b.real * ratio + b.imag
        return _AilComplex((a.real * ratio + a.imag) / denom,
                           (a.imag * ratio - a.real) / denom)
    return _AilComplex(_AIL_CM_NAN, _AIL_CM_NAN)


def _ail_cm_powu(x, n: int):
    r = _AilComplex(1.0, 0.0)
    p = _AilComplex(x.real, x.imag)
    mask = 1
    while mask > 0 and n >= mask:
        if n & mask:
            r = r.__mul__(p)
        mask = mask << 1
        p = p.__mul__(p)
    return r


def _ail_cm_powi(x, n: int):
    if n > 0:
        return _ail_cm_powu(x, n)
    d = _ail_cm_powu(x, -n)
    if d.real == 0.0 and d.imag == 0.0:
        raise ZeroDivisionError("0.0 to a negative or complex power")
    return _ail_cm_div(_AilComplex(1.0, 0.0), d)


def _ail_cm_fpow(x: float, y: float) -> float:
    if math.isnan(x) or math.isnan(y):
        if x == 1.0 or y == 0.0:
            return 1.0
        return _AIL_CM_NAN
    try:
        return math.pow(x, y)
    except OverflowError:
        return _AIL_CM_INF
    except ValueError:
        if x == 0.0 and y < 0.0:
            return _AIL_CM_INF
        return _AIL_CM_NAN


def _ail_cm_fexp(x: float) -> float:
    if math.isnan(x):
        return _AIL_CM_NAN
    try:
        return math.exp(x)
    except OverflowError:
        return _AIL_CM_INF


def _ail_cm_flog(x: float) -> float:
    if math.isnan(x):
        return _AIL_CM_NAN
    if x == 0.0:
        return -_AIL_CM_INF
    if x < 0.0:
        return _AIL_CM_NAN
    return math.log(x)


def _ail_cm_fdiv(a: float, b: float) -> float:
    if math.isnan(a) or math.isnan(b):
        return _AIL_CM_NAN
    if b == 0.0:
        if a == 0.0:
            return _AIL_CM_NAN
        return math.copysign(_AIL_CM_INF, a) * math.copysign(1.0, b)
    return a / b


def _ail_cm_pow(a, b):
    if b.real == 0.0 and b.imag == 0.0:
        return _AilComplex(1.0, 0.0)
    if a.real == 0.0 and a.imag == 0.0:
        if b.imag != 0.0 or b.real < 0.0:
            raise ZeroDivisionError("0.0 to a negative or complex power")
        return _AilComplex(0.0, 0.0)
    vabs = math.hypot(a.real, a.imag)
    length = _ail_cm_fpow(vabs, b.real)
    at = math.atan2(a.imag, a.real)
    phase = at * b.real
    if b.imag != 0.0:
        length = _ail_cm_fdiv(length, _ail_cm_fexp(at * b.imag))
        phase = phase + b.imag * _ail_cm_flog(vabs)
    edom = math.isinf(phase)
    if math.isnan(phase) or edom:
        real = _AIL_CM_NAN
        imag = _AIL_CM_NAN
    else:
        real = length * math.cos(phase)
        imag = length * math.sin(phase)
    if edom:
        raise ZeroDivisionError("0.0 to a negative or complex power")
    if math.isinf(real) or math.isinf(imag):
        raise OverflowError("complex exponentiation")
    return _AilComplex(real, imag)


def _ail_cm_cpow(a, b):
    return _ail_cm_pow(a, b)


def _ail_cm_atan2(z):
    if math.isnan(z.real) or math.isnan(z.imag):
        return _AIL_CM_NAN
    if math.isinf(z.imag):
        if math.isinf(z.real):
            if math.copysign(1.0, z.real) > 0.0:
                return math.copysign(0.25 * math.pi, z.imag)
            return math.copysign(0.75 * math.pi, z.imag)
        return math.copysign(0.5 * math.pi, z.imag)
    if math.isinf(z.real) or z.imag == 0.0:
        if math.copysign(1.0, z.real) > 0.0:
            return math.copysign(0.0, z.imag)
        return math.copysign(math.pi, z.imag)
    return math.atan2(z.imag, z.real)


def _ail_cm_sqrt(z):
    z = _ail_cm_arg(z)
    hit = _ail_cm_special(_AIL_CM_SQRT_SPECIAL, z)
    if hit is not None:
        return hit
    if z.real == 0.0 and z.imag == 0.0:
        return _AilComplex(0.0, z.imag)
    ax = abs(z.real)
    ay = abs(z.imag)
    if ax < 2.2250738585072014e-308 and ay < 2.2250738585072014e-308:
        ax = ax * 9007199254740992.0
        s = math.sqrt(ax + math.hypot(ax, ay * 9007199254740992.0)) * 7.450580596923828e-09
    else:
        ax = ax / 8.0
        s = 2.0 * math.sqrt(ax + math.hypot(ax, ay / 8.0))
    d = ay / (2.0 * s)
    if z.real >= 0.0:
        return _AilComplex(s, math.copysign(d, z.imag))
    return _AilComplex(d, math.copysign(s, z.imag))


def _ail_cm_log_value(z):
    hit = _ail_cm_special(_AIL_CM_LOG_SPECIAL, z)
    if hit is not None:
        return hit
    ax = abs(z.real)
    ay = abs(z.imag)
    if ax > _AIL_CM_LARGE or ay > _AIL_CM_LARGE:
        re = math.log(math.hypot(ax / 2.0, ay / 2.0)) + _AIL_CM_LN2
    elif ax < 2.2250738585072014e-308 and ay < 2.2250738585072014e-308:
        if ax > 0.0 or ay > 0.0:
            re = math.log(math.hypot(ax * 9007199254740992.0, ay * 9007199254740992.0)) - 53 * _AIL_CM_LN2
        else:
            raise ValueError("math domain error")
    else:
        h = math.hypot(ax, ay)
        if 0.71 <= h and h <= 1.73:
            am = ax if ax > ay else ay
            an = ay if ax > ay else ax
            re = math.log1p((am - 1.0) * (am + 1.0) + an * an) / 2.0
        else:
            re = math.log(h)
    return _AilComplex(re, math.atan2(z.imag, z.real))


def _ail_cm_log(z, base=None):
    x = _ail_cm_log_value(_ail_cm_arg(z))
    if base is not None:
        y = _ail_cm_log_value(_ail_cm_arg(base))
        if y.real == 0.0 and y.imag == 0.0:
            raise ValueError("math domain error")
        return _ail_cm_div(x, y)
    return x


def _ail_cm_log10(z):
    r = _ail_cm_log_value(_ail_cm_arg(z))
    return _AilComplex(r.real / _AIL_CM_LN10, r.imag / _AIL_CM_LN10)


def _ail_cm_exp(z):
    z = _ail_cm_arg(z)
    if not math.isfinite(z.real) or not math.isfinite(z.imag):
        if math.isinf(z.real) and math.isfinite(z.imag) and z.imag != 0.0:
            if z.real > 0.0:
                return _AilComplex(math.copysign(_AIL_CM_INF, math.cos(z.imag)),
                                   math.copysign(_AIL_CM_INF, math.sin(z.imag)))
            return _AilComplex(math.copysign(0.0, math.cos(z.imag)),
                               math.copysign(0.0, math.sin(z.imag)))
        if math.isinf(z.imag) and (math.isfinite(z.real) or (math.isinf(z.real) and z.real > 0.0)):
            raise ValueError("math domain error")
        return _ail_cm_special(_AIL_CM_EXP_SPECIAL, z)
    if z.real > _AIL_CM_LOG_LARGE:
        l = math.exp(z.real - 1.0)
        r = _AilComplex(l * math.cos(z.imag) * math.e, l * math.sin(z.imag) * math.e)
    else:
        l = math.exp(z.real)
        r = _AilComplex(l * math.cos(z.imag), l * math.sin(z.imag))
    if math.isinf(r.real) or math.isinf(r.imag):
        raise OverflowError("math range error")
    return r


def _ail_cm_cosh(z):
    z = _ail_cm_arg(z)
    if not math.isfinite(z.real) or not math.isfinite(z.imag):
        if math.isinf(z.real) and math.isfinite(z.imag) and z.imag != 0.0:
            if z.real > 0.0:
                return _AilComplex(math.copysign(_AIL_CM_INF, math.cos(z.imag)),
                                   math.copysign(_AIL_CM_INF, math.sin(z.imag)))
            return _AilComplex(math.copysign(_AIL_CM_INF, math.cos(z.imag)),
                               -math.copysign(_AIL_CM_INF, math.sin(z.imag)))
        r = _ail_cm_special(_AIL_CM_COSH_SPECIAL, z)
        if math.isinf(z.imag) and not math.isnan(z.real):
            raise ValueError("math domain error")
        return r
    if abs(z.real) > _AIL_CM_LOG_LARGE:
        x_minus_one = z.real - math.copysign(1.0, z.real)
        r = _AilComplex(math.cos(z.imag) * math.cosh(x_minus_one) * math.e,
                        math.sin(z.imag) * math.sinh(x_minus_one) * math.e)
    else:
        r = _AilComplex(math.cos(z.imag) * math.cosh(z.real),
                        math.sin(z.imag) * math.sinh(z.real))
    if math.isinf(r.real) or math.isinf(r.imag):
        raise OverflowError("math range error")
    return r


def _ail_cm_sinh(z):
    z = _ail_cm_arg(z)
    if not math.isfinite(z.real) or not math.isfinite(z.imag):
        if math.isinf(z.real) and math.isfinite(z.imag) and z.imag != 0.0:
            if z.real > 0.0:
                return _AilComplex(math.copysign(_AIL_CM_INF, math.cos(z.imag)),
                                   math.copysign(_AIL_CM_INF, math.sin(z.imag)))
            return _AilComplex(-math.copysign(_AIL_CM_INF, math.cos(z.imag)),
                               math.copysign(_AIL_CM_INF, math.sin(z.imag)))
        r = _ail_cm_special(_AIL_CM_SINH_SPECIAL, z)
        if math.isinf(z.imag) and not math.isnan(z.real):
            raise ValueError("math domain error")
        return r
    if abs(z.real) > _AIL_CM_LOG_LARGE:
        x_minus_one = z.real - math.copysign(1.0, z.real)
        r = _AilComplex(math.cos(z.imag) * math.sinh(x_minus_one) * math.e,
                        math.sin(z.imag) * math.cosh(x_minus_one) * math.e)
    else:
        r = _AilComplex(math.cos(z.imag) * math.sinh(z.real),
                        math.sin(z.imag) * math.cosh(z.real))
    if math.isinf(r.real) or math.isinf(r.imag):
        raise OverflowError("math range error")
    return r


def _ail_cm_tanh(z):
    z = _ail_cm_arg(z)
    if not math.isfinite(z.real) or not math.isfinite(z.imag):
        if math.isinf(z.real) and math.isfinite(z.imag) and z.imag != 0.0:
            if z.real > 0.0:
                return _AilComplex(1.0, math.copysign(0.0, 2.0 * math.sin(z.imag) * math.cos(z.imag)))
            return _AilComplex(-1.0, math.copysign(0.0, 2.0 * math.sin(z.imag) * math.cos(z.imag)))
        r = _ail_cm_special(_AIL_CM_TANH_SPECIAL, z)
        if math.isinf(z.imag) and math.isfinite(z.real):
            raise ValueError("math domain error")
        return r
    if abs(z.real) > _AIL_CM_LOG_LARGE:
        return _AilComplex(math.copysign(1.0, z.real),
                           4.0 * math.sin(z.imag) * math.cos(z.imag) * math.exp(-2.0 * abs(z.real)))
    tx = math.tanh(z.real)
    ty = math.tan(z.imag)
    cx = 1.0 / math.cosh(z.real)
    txty = tx * ty
    denom = 1.0 + txty * txty
    return _AilComplex(tx * (1.0 + ty * ty) / denom, ((ty / denom) * cx) * cx)


def _ail_cm_sin(z):
    z = _ail_cm_arg(z)
    s = _ail_cm_sinh(_AilComplex(-z.imag, z.real))
    return _AilComplex(s.imag, -s.real)


def _ail_cm_cos(z):
    z = _ail_cm_arg(z)
    return _ail_cm_cosh(_AilComplex(-z.imag, z.real))


def _ail_cm_tan(z):
    z = _ail_cm_arg(z)
    s = _ail_cm_tanh(_AilComplex(-z.imag, z.real))
    return _AilComplex(s.imag, -s.real)


def _ail_cm_asinh(z):
    z = _ail_cm_arg(z)
    hit = _ail_cm_special(_AIL_CM_ASINH_SPECIAL, z)
    if hit is not None:
        return hit
    if abs(z.real) > _AIL_CM_LARGE or abs(z.imag) > _AIL_CM_LARGE:
        if z.imag >= 0.0:
            re = math.copysign(math.log(math.hypot(z.real / 2.0, z.imag / 2.0)) + _AIL_CM_LN2 * 2.0,
                               z.real)
        else:
            re = -math.copysign(math.log(math.hypot(z.real / 2.0, z.imag / 2.0)) + _AIL_CM_LN2 * 2.0,
                                -z.real)
        return _AilComplex(re, math.atan2(z.imag, abs(z.real)))
    s1 = _ail_cm_sqrt(_AilComplex(1.0 + z.imag, -z.real))
    s2 = _ail_cm_sqrt(_AilComplex(1.0 - z.imag, z.real))
    return _AilComplex(math.asinh(s1.real * s2.imag - s2.real * s1.imag),
                       math.atan2(z.imag, s1.real * s2.real - s1.imag * s2.imag))


def _ail_cm_acos(z):
    z = _ail_cm_arg(z)
    hit = _ail_cm_special(_AIL_CM_ACOS_SPECIAL, z)
    if hit is not None:
        return hit
    if abs(z.real) > _AIL_CM_LARGE or abs(z.imag) > _AIL_CM_LARGE:
        re = math.atan2(abs(z.imag), z.real)
        if z.real < 0.0:
            im = -math.copysign(math.log(math.hypot(z.real / 2.0, z.imag / 2.0)) + _AIL_CM_LN2 * 2.0,
                                z.imag)
        else:
            im = math.copysign(math.log(math.hypot(z.real / 2.0, z.imag / 2.0)) + _AIL_CM_LN2 * 2.0,
                               -z.imag)
        return _AilComplex(re, im)
    s1 = _ail_cm_sqrt(_AilComplex(1.0 - z.real, -z.imag))
    s2 = _ail_cm_sqrt(_AilComplex(1.0 + z.real, z.imag))
    return _AilComplex(2.0 * math.atan2(s1.real, s2.real),
                       math.asinh(s2.real * s1.imag - s2.imag * s1.real))


def _ail_cm_acosh(z):
    z = _ail_cm_arg(z)
    hit = _ail_cm_special(_AIL_CM_ACOSH_SPECIAL, z)
    if hit is not None:
        return hit
    if abs(z.real) > _AIL_CM_LARGE or abs(z.imag) > _AIL_CM_LARGE:
        return _AilComplex(math.log(math.hypot(z.real / 2.0, z.imag / 2.0)) + _AIL_CM_LN2 * 2.0,
                           math.atan2(z.imag, z.real))
    s1 = _ail_cm_sqrt(_AilComplex(z.real - 1.0, z.imag))
    s2 = _ail_cm_sqrt(_AilComplex(z.real + 1.0, z.imag))
    return _AilComplex(math.asinh(s1.real * s2.real + s1.imag * s2.imag),
                       2.0 * math.atan2(s1.imag, s2.real))


def _ail_cm_asin(z):
    z = _ail_cm_arg(z)
    s = _ail_cm_asinh(_AilComplex(-z.imag, z.real))
    return _AilComplex(s.imag, -s.real)


def _ail_cm_atan(z):
    z = _ail_cm_arg(z)
    s = _ail_cm_atanh(_AilComplex(-z.imag, z.real))
    return _AilComplex(s.imag, -s.real)


def _ail_cm_atanh(z):
    z = _ail_cm_arg(z)
    hit = _ail_cm_special(_AIL_CM_ATANH_SPECIAL, z)
    if hit is not None:
        return hit
    if z.real < 0.0:
        s = _ail_cm_atanh(_AilComplex(-z.real, -z.imag))
        return _AilComplex(-s.real, -s.imag)
    ay = abs(z.imag)
    if z.real > _AIL_CM_SQRT_LARGE or ay > _AIL_CM_SQRT_LARGE:
        h = math.hypot(z.real / 2.0, z.imag / 2.0)
        return _AilComplex(z.real / 4.0 / h / h, -math.copysign(math.pi / 2.0, -z.imag))
    if z.real == 1.0 and ay < _AIL_CM_SQRT_DBL_MIN:
        if ay == 0.0:
            raise ValueError("math domain error")
        return _AilComplex(-math.log(math.sqrt(ay) / math.sqrt(math.hypot(ay, 2.0))),
                           math.copysign(math.atan2(2.0, -ay) / 2.0, z.imag))
    return _AilComplex(math.log1p(4.0 * z.real / ((1.0 - z.real) * (1.0 - z.real) + ay * ay)) / 4.0,
                       -math.atan2(-2.0 * z.imag, (1.0 - z.real) * (1.0 + z.real) - ay * ay) / 2.0)


def _ail_cm_phase(z):
    return _ail_cm_atan2(_ail_cm_arg(z))


def _ail_cm_polar(z):
    z = _ail_cm_arg(z)
    r = _ail_cm_abs(z)
    if math.isinf(r) and math.isfinite(z.real) and math.isfinite(z.imag):
        raise OverflowError("math range error")
    return (r, _ail_cm_atan2(z))


def _ail_cm_rect(r, phi):
    r = _ail_cm_float_arg(r)
    phi = _ail_cm_float_arg(phi)
    if not math.isfinite(r) or not math.isfinite(phi):
        if math.isinf(r) and math.isfinite(phi) and phi != 0.0:
            if r > 0.0:
                return _AilComplex(math.copysign(_AIL_CM_INF, math.cos(phi)),
                                   math.copysign(_AIL_CM_INF, math.sin(phi)))
            return _AilComplex(-math.copysign(_AIL_CM_INF, math.cos(phi)),
                               -math.copysign(_AIL_CM_INF, math.sin(phi)))
        if r != 0.0 and not math.isnan(r) and math.isinf(phi):
            raise ValueError("math domain error")
        i = 2 * (_ail_cm_typ(r) * 7 + _ail_cm_typ(phi))
        return _AilComplex(_AIL_CM_RECT_SPECIAL[i], _AIL_CM_RECT_SPECIAL[i + 1])
    if phi == 0.0:
        return _AilComplex(r, r * phi)
    return _AilComplex(r * math.cos(phi), r * math.sin(phi))


def _ail_cm_isfinite(z) -> bool:
    z = _ail_cm_arg(z)
    return math.isfinite(z.real) and math.isfinite(z.imag)


def _ail_cm_isnan(z) -> bool:
    z = _ail_cm_arg(z)
    return math.isnan(z.real) or math.isnan(z.imag)


def _ail_cm_isinf(z) -> bool:
    z = _ail_cm_arg(z)
    return math.isinf(z.real) or math.isinf(z.imag)


def _ail_cm_isclose(a, b, rel_tol=1e-09, abs_tol=0.0) -> bool:
    a = _ail_cm_arg(a)
    b = _ail_cm_arg(b)
    if rel_tol < 0.0 or abs_tol < 0.0:
        raise ValueError("tolerances must be non-negative")
    if a.real == b.real and a.imag == b.imag:
        return True
    if math.isinf(a.real) or math.isinf(a.imag) or math.isinf(b.real) or math.isinf(b.imag):
        return False
    diff = _ail_cm_abs(_AilComplex(a.real - b.real, a.imag - b.imag))
    return diff <= rel_tol * _ail_cm_abs(b) or diff <= rel_tol * _ail_cm_abs(a) or diff <= abs_tol

