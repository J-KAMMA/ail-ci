# python3 AIL_CURRENT/ail_bindgen.py /usr/include/math.h --cpp --header-name math.h --link m -o examples/ffi/bindgen/math_gen_ffi.py
from ail_ffi import *
link('m')

@extern(header='math.h')
def acos(__x: c_double) -> c_double: ...
@extern(header='math.h')
def asin(__x: c_double) -> c_double: ...
@extern(header='math.h')
def atan(__x: c_double) -> c_double: ...
@extern(header='math.h')
def atan2(__y: c_double, __x: c_double) -> c_double: ...
@extern(header='math.h')
def cos(__x: c_double) -> c_double: ...
@extern(header='math.h')
def sin(__x: c_double) -> c_double: ...
@extern(header='math.h')
def tan(__x: c_double) -> c_double: ...
@extern(header='math.h')
def cosh(__x: c_double) -> c_double: ...
@extern(header='math.h')
def sinh(__x: c_double) -> c_double: ...
@extern(header='math.h')
def tanh(__x: c_double) -> c_double: ...
@extern(header='math.h')
def acosh(__x: c_double) -> c_double: ...
@extern(header='math.h')
def asinh(__x: c_double) -> c_double: ...
@extern(header='math.h')
def atanh(__x: c_double) -> c_double: ...
@extern(header='math.h')
def exp(__x: c_double) -> c_double: ...
@extern(header='math.h')
def frexp(__x: c_double, __exponent: ptr(c_int)) -> c_double: ...
@extern(header='math.h')
def ldexp(__x: c_double, __exponent: c_int) -> c_double: ...
@extern(header='math.h')
def log(__x: c_double) -> c_double: ...
@extern(header='math.h')
def log10(__x: c_double) -> c_double: ...
@extern(header='math.h')
def modf(__x: c_double, __iptr: ptr(c_double)) -> c_double: ...
@extern(header='math.h')
def expm1(__x: c_double) -> c_double: ...
@extern(header='math.h')
def log1p(__x: c_double) -> c_double: ...
@extern(header='math.h')
def logb(__x: c_double) -> c_double: ...
@extern(header='math.h')
def exp2(__x: c_double) -> c_double: ...
@extern(header='math.h')
def log2(__x: c_double) -> c_double: ...
@extern(header='math.h')
def pow(__x: c_double, __y: c_double) -> c_double: ...
@extern(header='math.h')
def sqrt(__x: c_double) -> c_double: ...
@extern(header='math.h')
def hypot(__x: c_double, __y: c_double) -> c_double: ...
@extern(header='math.h')
def cbrt(__x: c_double) -> c_double: ...
@extern(header='math.h')
def ceil(__x: c_double) -> c_double: ...
@extern(header='math.h')
def fabs(__x: c_double) -> c_double: ...
@extern(header='math.h')
def floor(__x: c_double) -> c_double: ...
@extern(header='math.h')
def fmod(__x: c_double, __y: c_double) -> c_double: ...
@extern(header='math.h')
def copysign(__x: c_double, __y: c_double) -> c_double: ...
@extern(header='math.h')
def nan(__tagb: c_char_p) -> c_double: ...
@extern(header='math.h')
def erf(a0: c_double) -> c_double: ...
@extern(header='math.h')
def erfc(a0: c_double) -> c_double: ...
@extern(header='math.h')
def lgamma(a0: c_double) -> c_double: ...
@extern(header='math.h')
def tgamma(a0: c_double) -> c_double: ...
@extern(header='math.h')
def rint(__x: c_double) -> c_double: ...
@extern(header='math.h')
def nextafter(__x: c_double, __y: c_double) -> c_double: ...
@extern(header='math.h')
def remainder(__x: c_double, __y: c_double) -> c_double: ...
@extern(header='math.h')
def scalbn(__x: c_double, __n: c_int) -> c_double: ...
@extern(header='math.h')
def ilogb(__x: c_double) -> c_int: ...
@extern(header='math.h')
def scalbln(__x: c_double, __n: c_long) -> c_double: ...
@extern(header='math.h')
def nearbyint(__x: c_double) -> c_double: ...
@extern(header='math.h')
def round(__x: c_double) -> c_double: ...
@extern(header='math.h')
def trunc(__x: c_double) -> c_double: ...
@extern(header='math.h')
def remquo(__x: c_double, __y: c_double, __quo: ptr(c_int)) -> c_double: ...
@extern(header='math.h')
def lrint(__x: c_double) -> c_long: ...
@extern(header='math.h')
def llrint(__x: c_double) -> c_longlong: ...
@extern(header='math.h')
def lround(__x: c_double) -> c_long: ...
@extern(header='math.h')
def llround(__x: c_double) -> c_longlong: ...
@extern(header='math.h')
def fdim(__x: c_double, __y: c_double) -> c_double: ...
@extern(header='math.h')
def fmax(__x: c_double, __y: c_double) -> c_double: ...
@extern(header='math.h')
def fmin(__x: c_double, __y: c_double) -> c_double: ...
@extern(header='math.h')
def fma(__x: c_double, __y: c_double, __z: c_double) -> c_double: ...
@extern(header='math.h')
def acosf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def asinf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def atanf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def atan2f(__y: c_float, __x: c_float) -> c_float: ...
@extern(header='math.h')
def cosf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def sinf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def tanf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def coshf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def sinhf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def tanhf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def acoshf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def asinhf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def atanhf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def expf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def frexpf(__x: c_float, __exponent: ptr(c_int)) -> c_float: ...
@extern(header='math.h')
def ldexpf(__x: c_float, __exponent: c_int) -> c_float: ...
@extern(header='math.h')
def logf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def log10f(__x: c_float) -> c_float: ...
@extern(header='math.h')
def modff(__x: c_float, __iptr: ptr(c_float)) -> c_float: ...
@extern(header='math.h')
def expm1f(__x: c_float) -> c_float: ...
@extern(header='math.h')
def log1pf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def logbf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def exp2f(__x: c_float) -> c_float: ...
@extern(header='math.h')
def log2f(__x: c_float) -> c_float: ...
@extern(header='math.h')
def powf(__x: c_float, __y: c_float) -> c_float: ...
@extern(header='math.h')
def sqrtf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def hypotf(__x: c_float, __y: c_float) -> c_float: ...
@extern(header='math.h')
def cbrtf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def ceilf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def fabsf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def floorf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def fmodf(__x: c_float, __y: c_float) -> c_float: ...
@extern(header='math.h')
def copysignf(__x: c_float, __y: c_float) -> c_float: ...
@extern(header='math.h')
def nanf(__tagb: c_char_p) -> c_float: ...
@extern(header='math.h')
def erff(a0: c_float) -> c_float: ...
@extern(header='math.h')
def erfcf(a0: c_float) -> c_float: ...
@extern(header='math.h')
def lgammaf(a0: c_float) -> c_float: ...
@extern(header='math.h')
def tgammaf(a0: c_float) -> c_float: ...
@extern(header='math.h')
def rintf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def nextafterf(__x: c_float, __y: c_float) -> c_float: ...
@extern(header='math.h')
def remainderf(__x: c_float, __y: c_float) -> c_float: ...
@extern(header='math.h')
def scalbnf(__x: c_float, __n: c_int) -> c_float: ...
@extern(header='math.h')
def ilogbf(__x: c_float) -> c_int: ...
@extern(header='math.h')
def scalblnf(__x: c_float, __n: c_long) -> c_float: ...
@extern(header='math.h')
def nearbyintf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def roundf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def truncf(__x: c_float) -> c_float: ...
@extern(header='math.h')
def remquof(__x: c_float, __y: c_float, __quo: ptr(c_int)) -> c_float: ...
@extern(header='math.h')
def lrintf(__x: c_float) -> c_long: ...
@extern(header='math.h')
def llrintf(__x: c_float) -> c_longlong: ...
@extern(header='math.h')
def lroundf(__x: c_float) -> c_long: ...
@extern(header='math.h')
def llroundf(__x: c_float) -> c_longlong: ...
@extern(header='math.h')
def fdimf(__x: c_float, __y: c_float) -> c_float: ...
@extern(header='math.h')
def fmaxf(__x: c_float, __y: c_float) -> c_float: ...
@extern(header='math.h')
def fminf(__x: c_float, __y: c_float) -> c_float: ...
@extern(header='math.h')
def fmaf(__x: c_float, __y: c_float, __z: c_float) -> c_float: ...
# skipped __fpclassify: a name reserved for the C implementation
# skipped __signbit: a name reserved for the C implementation
# skipped __isinf: a name reserved for the C implementation
# skipped __finite: a name reserved for the C implementation
# skipped __isnan: a name reserved for the C implementation
# skipped __iseqsig: a name reserved for the C implementation
# skipped __issignaling: a name reserved for the C implementation
# skipped __acos: a name reserved for the C implementation
# skipped __asin: a name reserved for the C implementation
# skipped __atan: a name reserved for the C implementation
# skipped __atan2: a name reserved for the C implementation
# skipped __cos: a name reserved for the C implementation
# skipped __sin: a name reserved for the C implementation
# skipped __tan: a name reserved for the C implementation
# skipped __cosh: a name reserved for the C implementation
# skipped __sinh: a name reserved for the C implementation
# skipped __tanh: a name reserved for the C implementation
# skipped __acosh: a name reserved for the C implementation
# skipped __asinh: a name reserved for the C implementation
# skipped __atanh: a name reserved for the C implementation
# skipped __exp: a name reserved for the C implementation
# skipped __frexp: a name reserved for the C implementation
# skipped __ldexp: a name reserved for the C implementation
# skipped __log: a name reserved for the C implementation
# skipped __log10: a name reserved for the C implementation
# skipped __modf: a name reserved for the C implementation
# skipped __expm1: a name reserved for the C implementation
# skipped __log1p: a name reserved for the C implementation
# skipped __logb: a name reserved for the C implementation
# skipped __exp2: a name reserved for the C implementation
# skipped __log2: a name reserved for the C implementation
# skipped __pow: a name reserved for the C implementation
# skipped __sqrt: a name reserved for the C implementation
# skipped __hypot: a name reserved for the C implementation
# skipped __cbrt: a name reserved for the C implementation
# skipped __ceil: a name reserved for the C implementation
# skipped __fabs: a name reserved for the C implementation
# skipped __floor: a name reserved for the C implementation
# skipped __fmod: a name reserved for the C implementation
# skipped isinf: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped finite: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped drem: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __drem: a name reserved for the C implementation
# skipped significand: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __significand: a name reserved for the C implementation
# skipped __copysign: a name reserved for the C implementation
# skipped __nan: a name reserved for the C implementation
# skipped isnan: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped j0: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __j0: a name reserved for the C implementation
# skipped j1: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __j1: a name reserved for the C implementation
# skipped jn: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __jn: a name reserved for the C implementation
# skipped y0: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __y0: a name reserved for the C implementation
# skipped y1: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __y1: a name reserved for the C implementation
# skipped yn: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __yn: a name reserved for the C implementation
# skipped __erf: a name reserved for the C implementation
# skipped __erfc: a name reserved for the C implementation
# skipped __lgamma: a name reserved for the C implementation
# skipped __tgamma: a name reserved for the C implementation
# skipped gamma: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __gamma: a name reserved for the C implementation
# skipped lgamma_r: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __lgamma_r: a name reserved for the C implementation
# skipped __rint: a name reserved for the C implementation
# skipped __nextafter: a name reserved for the C implementation
# skipped nexttoward: unknown or struct-by-value type 'long double' (use --typedef NAME=c_type)
# skipped __nexttoward: a name reserved for the C implementation
# skipped __remainder: a name reserved for the C implementation
# skipped __scalbn: a name reserved for the C implementation
# skipped __ilogb: a name reserved for the C implementation
# skipped __scalbln: a name reserved for the C implementation
# skipped __nearbyint: a name reserved for the C implementation
# skipped __round: a name reserved for the C implementation
# skipped __trunc: a name reserved for the C implementation
# skipped __remquo: a name reserved for the C implementation
# skipped __lrint: a name reserved for the C implementation
# skipped __llrint: a name reserved for the C implementation
# skipped __lround: a name reserved for the C implementation
# skipped __llround: a name reserved for the C implementation
# skipped __fdim: a name reserved for the C implementation
# skipped __fmax: a name reserved for the C implementation
# skipped __fmin: a name reserved for the C implementation
# skipped __fma: a name reserved for the C implementation
# skipped scalb: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __scalb: a name reserved for the C implementation
# skipped __fpclassifyf: a name reserved for the C implementation
# skipped __signbitf: a name reserved for the C implementation
# skipped __isinff: a name reserved for the C implementation
# skipped __finitef: a name reserved for the C implementation
# skipped __isnanf: a name reserved for the C implementation
# skipped __iseqsigf: a name reserved for the C implementation
# skipped __issignalingf: a name reserved for the C implementation
# skipped __acosf: a name reserved for the C implementation
# skipped __asinf: a name reserved for the C implementation
# skipped __atanf: a name reserved for the C implementation
# skipped __atan2f: a name reserved for the C implementation
# skipped __cosf: a name reserved for the C implementation
# skipped __sinf: a name reserved for the C implementation
# skipped __tanf: a name reserved for the C implementation
# skipped __coshf: a name reserved for the C implementation
# skipped __sinhf: a name reserved for the C implementation
# skipped __tanhf: a name reserved for the C implementation
# skipped __acoshf: a name reserved for the C implementation
# skipped __asinhf: a name reserved for the C implementation
# skipped __atanhf: a name reserved for the C implementation
# skipped __expf: a name reserved for the C implementation
# skipped __frexpf: a name reserved for the C implementation
# skipped __ldexpf: a name reserved for the C implementation
# skipped __logf: a name reserved for the C implementation
# skipped __log10f: a name reserved for the C implementation
# skipped __modff: a name reserved for the C implementation
# skipped __expm1f: a name reserved for the C implementation
# skipped __log1pf: a name reserved for the C implementation
# skipped __logbf: a name reserved for the C implementation
# skipped __exp2f: a name reserved for the C implementation
# skipped __log2f: a name reserved for the C implementation
# skipped __powf: a name reserved for the C implementation
# skipped __sqrtf: a name reserved for the C implementation
# skipped __hypotf: a name reserved for the C implementation
# skipped __cbrtf: a name reserved for the C implementation
# skipped __ceilf: a name reserved for the C implementation
# skipped __fabsf: a name reserved for the C implementation
# skipped __floorf: a name reserved for the C implementation
# skipped __fmodf: a name reserved for the C implementation
# skipped isinff: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped finitef: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped dremf: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __dremf: a name reserved for the C implementation
# skipped significandf: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __significandf: a name reserved for the C implementation
# skipped __copysignf: a name reserved for the C implementation
# skipped __nanf: a name reserved for the C implementation
# skipped isnanf: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped j0f: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __j0f: a name reserved for the C implementation
# skipped j1f: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __j1f: a name reserved for the C implementation
# skipped jnf: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __jnf: a name reserved for the C implementation
# skipped y0f: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __y0f: a name reserved for the C implementation
# skipped y1f: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __y1f: a name reserved for the C implementation
# skipped ynf: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __ynf: a name reserved for the C implementation
# skipped __erff: a name reserved for the C implementation
# skipped __erfcf: a name reserved for the C implementation
# skipped __lgammaf: a name reserved for the C implementation
# skipped __tgammaf: a name reserved for the C implementation
# skipped gammaf: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __gammaf: a name reserved for the C implementation
# skipped lgammaf_r: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __lgammaf_r: a name reserved for the C implementation
# skipped __rintf: a name reserved for the C implementation
# skipped __nextafterf: a name reserved for the C implementation
# skipped nexttowardf: unknown or struct-by-value type 'long double' (use --typedef NAME=c_type)
# skipped __nexttowardf: a name reserved for the C implementation
# skipped __remainderf: a name reserved for the C implementation
# skipped __scalbnf: a name reserved for the C implementation
# skipped __ilogbf: a name reserved for the C implementation
# skipped __scalblnf: a name reserved for the C implementation
# skipped __nearbyintf: a name reserved for the C implementation
# skipped __roundf: a name reserved for the C implementation
# skipped __truncf: a name reserved for the C implementation
# skipped __remquof: a name reserved for the C implementation
# skipped __lrintf: a name reserved for the C implementation
# skipped __llrintf: a name reserved for the C implementation
# skipped __lroundf: a name reserved for the C implementation
# skipped __llroundf: a name reserved for the C implementation
# skipped __fdimf: a name reserved for the C implementation
# skipped __fmaxf: a name reserved for the C implementation
# skipped __fminf: a name reserved for the C implementation
# skipped __fmaf: a name reserved for the C implementation
# skipped scalbf: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __scalbf: a name reserved for the C implementation
# skipped __fpclassifyl: a name reserved for the C implementation
# skipped __signbitl: a name reserved for the C implementation
# skipped __isinfl: a name reserved for the C implementation
# skipped __finitel: a name reserved for the C implementation
# skipped __isnanl: a name reserved for the C implementation
# skipped __iseqsigl: a name reserved for the C implementation
# skipped __issignalingl: a name reserved for the C implementation
# skipped acosl: unknown or struct result type 'long double'
# skipped __acosl: a name reserved for the C implementation
# skipped asinl: unknown or struct result type 'long double'
# skipped __asinl: a name reserved for the C implementation
# skipped atanl: unknown or struct result type 'long double'
# skipped __atanl: a name reserved for the C implementation
# skipped atan2l: unknown or struct result type 'long double'
# skipped __atan2l: a name reserved for the C implementation
# skipped cosl: unknown or struct result type 'long double'
# skipped __cosl: a name reserved for the C implementation
# skipped sinl: unknown or struct result type 'long double'
# skipped __sinl: a name reserved for the C implementation
# skipped tanl: unknown or struct result type 'long double'
# skipped __tanl: a name reserved for the C implementation
# skipped coshl: unknown or struct result type 'long double'
# skipped __coshl: a name reserved for the C implementation
# skipped sinhl: unknown or struct result type 'long double'
# skipped __sinhl: a name reserved for the C implementation
# skipped tanhl: unknown or struct result type 'long double'
# skipped __tanhl: a name reserved for the C implementation
# skipped acoshl: unknown or struct result type 'long double'
# skipped __acoshl: a name reserved for the C implementation
# skipped asinhl: unknown or struct result type 'long double'
# skipped __asinhl: a name reserved for the C implementation
# skipped atanhl: unknown or struct result type 'long double'
# skipped __atanhl: a name reserved for the C implementation
# skipped expl: unknown or struct result type 'long double'
# skipped __expl: a name reserved for the C implementation
# skipped frexpl: unknown or struct result type 'long double'
# skipped __frexpl: a name reserved for the C implementation
# skipped ldexpl: unknown or struct result type 'long double'
# skipped __ldexpl: a name reserved for the C implementation
# skipped logl: unknown or struct result type 'long double'
# skipped __logl: a name reserved for the C implementation
# skipped log10l: unknown or struct result type 'long double'
# skipped __log10l: a name reserved for the C implementation
# skipped modfl: unknown or struct result type 'long double'
# skipped __modfl: a name reserved for the C implementation
# skipped expm1l: unknown or struct result type 'long double'
# skipped __expm1l: a name reserved for the C implementation
# skipped log1pl: unknown or struct result type 'long double'
# skipped __log1pl: a name reserved for the C implementation
# skipped logbl: unknown or struct result type 'long double'
# skipped __logbl: a name reserved for the C implementation
# skipped exp2l: unknown or struct result type 'long double'
# skipped __exp2l: a name reserved for the C implementation
# skipped log2l: unknown or struct result type 'long double'
# skipped __log2l: a name reserved for the C implementation
# skipped powl: unknown or struct result type 'long double'
# skipped __powl: a name reserved for the C implementation
# skipped sqrtl: unknown or struct result type 'long double'
# skipped __sqrtl: a name reserved for the C implementation
# skipped hypotl: unknown or struct result type 'long double'
# skipped __hypotl: a name reserved for the C implementation
# skipped cbrtl: unknown or struct result type 'long double'
# skipped __cbrtl: a name reserved for the C implementation
# skipped ceill: unknown or struct result type 'long double'
# skipped __ceill: a name reserved for the C implementation
# skipped fabsl: unknown or struct result type 'long double'
# skipped __fabsl: a name reserved for the C implementation
# skipped floorl: unknown or struct result type 'long double'
# skipped __floorl: a name reserved for the C implementation
# skipped fmodl: unknown or struct result type 'long double'
# skipped __fmodl: a name reserved for the C implementation
# skipped isinfl: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped finitel: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped dreml: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __dreml: a name reserved for the C implementation
# skipped significandl: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __significandl: a name reserved for the C implementation
# skipped copysignl: unknown or struct result type 'long double'
# skipped __copysignl: a name reserved for the C implementation
# skipped nanl: unknown or struct result type 'long double'
# skipped __nanl: a name reserved for the C implementation
# skipped isnanl: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped j0l: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __j0l: a name reserved for the C implementation
# skipped j1l: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __j1l: a name reserved for the C implementation
# skipped jnl: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __jnl: a name reserved for the C implementation
# skipped y0l: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __y0l: a name reserved for the C implementation
# skipped y1l: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __y1l: a name reserved for the C implementation
# skipped ynl: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __ynl: a name reserved for the C implementation
# skipped erfl: unknown or struct result type 'long double'
# skipped __erfl: a name reserved for the C implementation
# skipped erfcl: unknown or struct result type 'long double'
# skipped __erfcl: a name reserved for the C implementation
# skipped lgammal: unknown or struct result type 'long double'
# skipped __lgammal: a name reserved for the C implementation
# skipped tgammal: unknown or struct result type 'long double'
# skipped __tgammal: a name reserved for the C implementation
# skipped gammal: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __gammal: a name reserved for the C implementation
# skipped lgammal_r: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __lgammal_r: a name reserved for the C implementation
# skipped rintl: unknown or struct result type 'long double'
# skipped __rintl: a name reserved for the C implementation
# skipped nextafterl: unknown or struct result type 'long double'
# skipped __nextafterl: a name reserved for the C implementation
# skipped nexttowardl: unknown or struct result type 'long double'
# skipped __nexttowardl: a name reserved for the C implementation
# skipped remainderl: unknown or struct result type 'long double'
# skipped __remainderl: a name reserved for the C implementation
# skipped scalbnl: unknown or struct result type 'long double'
# skipped __scalbnl: a name reserved for the C implementation
# skipped ilogbl: unknown or struct-by-value type 'long double' (use --typedef NAME=c_type)
# skipped __ilogbl: a name reserved for the C implementation
# skipped scalblnl: unknown or struct result type 'long double'
# skipped __scalblnl: a name reserved for the C implementation
# skipped nearbyintl: unknown or struct result type 'long double'
# skipped __nearbyintl: a name reserved for the C implementation
# skipped roundl: unknown or struct result type 'long double'
# skipped __roundl: a name reserved for the C implementation
# skipped truncl: unknown or struct result type 'long double'
# skipped __truncl: a name reserved for the C implementation
# skipped remquol: unknown or struct result type 'long double'
# skipped __remquol: a name reserved for the C implementation
# skipped lrintl: unknown or struct-by-value type 'long double' (use --typedef NAME=c_type)
# skipped __lrintl: a name reserved for the C implementation
# skipped llrintl: unknown or struct-by-value type 'long double' (use --typedef NAME=c_type)
# skipped __llrintl: a name reserved for the C implementation
# skipped lroundl: unknown or struct-by-value type 'long double' (use --typedef NAME=c_type)
# skipped __lroundl: a name reserved for the C implementation
# skipped llroundl: unknown or struct-by-value type 'long double' (use --typedef NAME=c_type)
# skipped __llroundl: a name reserved for the C implementation
# skipped fdiml: unknown or struct result type 'long double'
# skipped __fdiml: a name reserved for the C implementation
# skipped fmaxl: unknown or struct result type 'long double'
# skipped __fmaxl: a name reserved for the C implementation
# skipped fminl: unknown or struct result type 'long double'
# skipped __fminl: a name reserved for the C implementation
# skipped fmal: unknown or struct result type 'long double'
# skipped __fmal: a name reserved for the C implementation
# skipped scalbl: the header does not declare it under -std=c11, the mode the prototype check is compiled in
# skipped __scalbl: a name reserved for the C implementation
# skipped __fpclassifyf128: a name reserved for the C implementation
# skipped __signbitf128: a name reserved for the C implementation
# skipped __isinff128: a name reserved for the C implementation
# skipped __finitef128: a name reserved for the C implementation
# skipped __isnanf128: a name reserved for the C implementation
# skipped __iseqsigf128: a name reserved for the C implementation
# skipped __issignalingf128: a name reserved for the C implementation
