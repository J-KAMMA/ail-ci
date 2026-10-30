"""Typed arrays with declared element types: the pure-Python reference of `ail_array` (stage T1).

The meaning of every operation is defined in docs/design/TYPED_ARRAY.md. This file implements exactly that meaning on
plain CPython 3.12 (standard library only, no numpy), and it is the oracle AIL's native lowering is compared with:
a program that imports `ail_array` prints, under CPython with this file beside it, what its AIL build must print.

    import ail_array as ta
    a = ta.array([1.0, 2.5, -0.0], ta.f32)
    y = (a * 2.0 + a) / 3.0          # every op rounded to f32, nothing fused
    print(ta.sum(y), y.tobytes().hex())

Dtypes: f64, f32, f16 (IEEE binary64/32/16), int8, int32, int64 and bool_ (stage T3b). Arrays are 1-D; 2-D arrays and
matmul are T6 (`mm` is the flat form that stage T3b adds for the torch layer).

How the bits are made (design sections 3 and 4):
* Float ops compute in binary64 (Python floats, correctly rounded) and round once to the dtype with `struct`. For
  `+ - * /` and sqrt that equals one correct rounding in the dtype (53 >= 2p + 2 for p = 24 and p = 11).
* Overflow goes to +-inf (`struct` raises instead, so the overflow is caught); division by zero is IEEE; subnormals
  are kept; every NaN an operation produces is the canonical positive quiet NaN. Bits that come in through
  `frombytes` are stored unchanged until an operation touches them.
* int8/int32/int64 `+ - * // %`, unary `-` and `abs` are exact and raise OverflowError at the first index whose result does
  not fit; `wrapping_*` and `saturating_*` are the explicit alternatives. bool_ has no arithmetic: comparisons give bool_
  arrays, `logical_*` and `where` combine them, `astype` converts.
* `sum` and `dot` of floats use one fixed order: blocks of 1024 elements, 16 lanes per block starting at -0.0, an
  8-4-2-1 tree over the lanes, and a power-of-two tree over the blocks.
"""
import builtins
import math
import struct

__all__ = ['DType', 'Array', 'f64', 'f32', 'f16', 'int8', 'int32', 'int64', 'bool_', 'array', 'zeros', 'full', 'arange',
           'frombytes', 'sqrt', 'exp', 'log', 'tanh', 'minimum', 'maximum', 'clip', 'wrapping_add', 'wrapping_sub',
           'wrapping_mul', 'wrapping_neg', 'wrapping_abs', 'wrapping_floordiv', 'wrapping_sum', 'wrapping_dot',
           'saturating_add', 'saturating_sub', 'sum', 'dot', 'min', 'max', 'argmin', 'argmax',
           'eq', 'ne', 'lt', 'le', 'gt', 'ge', 'logical_and', 'logical_or', 'logical_xor', 'logical_not', 'where', 'any',
           'all', 'take', 'put', 'gather_strided', 'scatter_strided', 'segment_sum', 'segment_min', 'segment_max',
           'segment_argmin', 'segment_argmax', 'wrapping_segment_sum', 'mm', 'promote_types', 'promote_scalar']

BLOCK = 1024
LANES = 16


class DType:
    """One of the seven element types. Compare with `is`; `repr` is the name."""
    __slots__ = ('name', 'itemsize', 'code', 'is_float', 'lo', 'hi', 'bits', 'is_bool')

    def __init__(self, name, itemsize, code, is_float, bits, is_bool=False):
        self.name, self.itemsize, self.code, self.is_float, self.bits = name, itemsize, code, is_float, bits
        self.is_bool = is_bool
        self.lo = None if is_float else (0 if is_bool else -(1 << (bits - 1)))
        self.hi = None if is_float else (1 if is_bool else (1 << (bits - 1)) - 1)

    def __repr__(self):
        return self.name

    def __reduce__(self):
        return self.name


f64 = DType('f64', 8, 'd', True, 64)
f32 = DType('f32', 4, 'f', True, 32)
f16 = DType('f16', 2, 'e', True, 16)
int8 = DType('int8', 1, 'b', False, 8)
int32 = DType('int32', 4, 'i', False, 32)
int64 = DType('int64', 8, 'q', False, 64)
bool_ = DType('bool_', 1, '?', False, 8, True)
_DTYPES = (f64, f32, f16, int8, int32, int64, bool_)
_WIDTH = {f16: 1, f32: 2, f64: 3}

# The canonical quiet NaN, sign bit clear (binary64 7ff8000000000000; packs to f32 7fc00000 and f16 7e00).
_NAN = struct.unpack('<d', bytes.fromhex('000000000000f87f'))[0]
_INF = float('inf')
_ONE = {code: struct.Struct('<' + code) for code in 'dfe'}


def _dtype(dt):
    if not isinstance(dt, DType):
        raise TypeError('ail_array: dtype must be one of f64, f32, f16, int8, int32, int64, bool_, not %s'
                        % type(dt).__name__)
    return dt


def _round(dt, x):
    """r_T(x) of one Python float: nearest-even, overflow to +-inf, NaN canonical."""
    if x != x:
        return _NAN
    if dt is f64:
        return x
    one = _ONE[dt.code]
    try:
        return one.unpack(one.pack(x))[0]
    except OverflowError:
        return math.copysign(_INF, x)


def _pack(dt, values):
    """Storage bytes of Python numbers that already are values of `dt` (rounded floats or in-range ints)."""
    if not values:
        return bytearray()
    if dt.is_float:
        values = [_NAN if v != v else v for v in values]
    return bytearray(struct.pack('<%d%s' % (len(values), dt.code), *values))


def _type_name(x):
    return type(x).__name__


def _store(dt, x):
    """The store rule: a Python value written into an array of `dt` (design 3.3, 3.4)."""
    if dt.is_float:
        if isinstance(x, float):
            return _round(dt, x)
        if isinstance(x, int):
            return _round(dt, float(x))
        raise TypeError('must be real number, not %s' % _type_name(x))
    if isinstance(x, int):
        v = int(x)
        if dt.is_bool:
            return v != 0
        if v < dt.lo or v > dt.hi:
            raise OverflowError('%s value out of range: %d' % (dt.name, v))
        return v
    raise TypeError("'%s' object cannot be interpreted as an integer" % _type_name(x))


class _Alias:
    __slots__ = ('dtype',)

    def __init__(self, dtype):
        self.dtype = dtype

    def __repr__(self):
        return 'Array[%s]' % self.dtype


class Array:
    """A fixed-length 1-D array of one dtype, stored little-endian in a bytearray (the native layout)."""
    __slots__ = ('_dt', '_n', '_buf')
    __hash__ = None

    def __class_getitem__(cls, dtype):
        return _Alias(dtype)

    # ---- construction helpers -------------------------------------------------------------------------------------
    @classmethod
    def _make(cls, dt, buf):
        a = object.__new__(cls)
        a._dt, a._n, a._buf = dt, len(buf) // dt.itemsize, buf
        return a

    @classmethod
    def _of(cls, dt, values):
        return cls._make(dt, _pack(dt, values))

    def _values(self):
        return list(struct.unpack_from('<%d%s' % (self._n, self._dt.code), self._buf))

    # ---- size -----------------------------------------------------------------------------------------------------
    @property
    def dtype(self):
        return self._dt

    @property
    def shape(self):
        return (self._n,)

    def __len__(self):
        return self._n

    # ---- indexing and slicing -------------------------------------------------------------------------------------
    def _index(self, i):
        if isinstance(i, int):
            i = int(i)
        elif hasattr(type(i), '__index__'):
            i = type(i).__index__(i)
        else:
            raise TypeError('array indices must be integers')
        if i < 0:
            i += self._n
        if i < 0 or i >= self._n:
            raise IndexError('array index out of range')
        return i

    def __getitem__(self, i):
        size = self._dt.itemsize
        if isinstance(i, slice):
            buf = self._buf
            out = bytearray()
            for k in range(*i.indices(self._n)):
                out += buf[k * size:(k + 1) * size]
            return Array._make(self._dt, out)
        k = self._index(i)
        return _ONE_READ[self._dt].unpack_from(self._buf, k * size)[0]

    def __setitem__(self, i, x):
        size = self._dt.itemsize
        if isinstance(i, slice):
            if not isinstance(x, Array):
                raise TypeError('ail_array: can only assign an ail_array.Array to a slice, not %s' % _type_name(x))
            if x._dt is not self._dt:
                raise TypeError('ail_array: slice assignment: dtypes differ (%s and %s)' % (self._dt, x._dt))
            ks = range(*i.indices(self._n))
            if len(ks) != x._n:
                raise ValueError('ail_array: slice assignment needs %d elements, not %d' % (len(ks), x._n))
            src = bytes(x._buf)
            for j, k in enumerate(ks):
                self._buf[k * size:(k + 1) * size] = src[j * size:(j + 1) * size]
            return
        k = self._index(i)
        v = _store(self._dt, x)
        self._buf[k * size:(k + 1) * size] = _pack(self._dt, [v])

    def __iter__(self):
        for k in range(self._n):
            yield self[k]

    def __contains__(self, x):
        return builtins.any(v == x for v in self._values())

    # ---- conversion -----------------------------------------------------------------------------------------------
    def tolist(self):
        return self._values()

    def tobytes(self):
        return bytes(self._buf)

    def copy(self):
        return Array._make(self._dt, bytearray(self._buf))

    def astype(self, dtype, rounding='trunc', overflow='raise'):
        return _astype(self, _dtype(dtype), rounding, overflow)

    # ---- comparison and text --------------------------------------------------------------------------------------
    def __eq__(self, other):
        if not isinstance(other, Array):
            return NotImplemented
        return self._dt is other._dt and self._n == other._n and self._values() == other._values()

    def __ne__(self, other):
        r = self.__eq__(other)
        return r if r is NotImplemented else not r

    def __repr__(self):
        return 'array([%s], %s)' % (', '.join(repr(v) for v in self._values()), self._dt.name)

    __str__ = __repr__

    # ---- arithmetic -----------------------------------------------------------------------------------------------
    def __add__(self, o): return _binary(self, o, '+', False)
    def __radd__(self, o): return _binary(self, o, '+', True)
    def __sub__(self, o): return _binary(self, o, '-', False)
    def __rsub__(self, o): return _binary(self, o, '-', True)
    def __mul__(self, o): return _binary(self, o, '*', False)
    def __rmul__(self, o): return _binary(self, o, '*', True)
    def __truediv__(self, o): return _binary(self, o, '/', False)
    def __rtruediv__(self, o): return _binary(self, o, '/', True)
    def __floordiv__(self, o): return _binary(self, o, '//', False)
    def __rfloordiv__(self, o): return _binary(self, o, '//', True)
    def __mod__(self, o): return _binary(self, o, '%', False)
    def __rmod__(self, o): return _binary(self, o, '%', True)
    def __iadd__(self, o): return _binary(self, o, '+', False, self)
    def __isub__(self, o): return _binary(self, o, '-', False, self)
    def __imul__(self, o): return _binary(self, o, '*', False, self)
    def __itruediv__(self, o): return _binary(self, o, '/', False, self)
    def __ifloordiv__(self, o): return _binary(self, o, '//', False, self)
    def __imod__(self, o): return _binary(self, o, '%', False, self)

    def __neg__(self):
        return _unary(self, 'neg')

    def __abs__(self):
        return _unary(self, 'abs')


_ONE_READ = {dt: struct.Struct('<' + dt.code) for dt in _DTYPES}


# ---- construction -------------------------------------------------------------------------------------------------
def _length(shape):
    if isinstance(shape, tuple):
        if len(shape) == 1:
            shape = shape[0]
        elif len(shape) == 2:
            raise ValueError('ail_array: 2-D arrays are not in this version (stage T6); shape %r' % (shape,))
        else:
            raise ValueError('ail_array has 1-D and 2-D arrays; shape %r' % (shape,))
    if isinstance(shape, builtins.bool) or not isinstance(shape, int):
        raise TypeError('ail_array: a length must be an int, not %s' % _type_name(shape))
    if shape < 0:
        raise ValueError('ail_array: negative length %d' % shape)
    return shape


def array(values, dtype):
    """A new array of `dtype` from an iterable of int/float/bool; every value goes through the store rule."""
    dt = _dtype(dtype)
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError('ail_array: array() needs an iterable of numbers, not %s' % _type_name(values))
    return Array._of(dt, [_store(dt, x) for x in values])


def zeros(shape, dtype):
    dt = _dtype(dtype)
    return Array._make(dt, bytearray(_length(shape) * dt.itemsize))


def full(shape, value, dtype):
    dt = _dtype(dtype)
    n = _length(shape)
    return Array._of(dt, [_store(dt, value)] * n)


def arange(n, dtype):
    dt = _dtype(dtype)
    if dt.is_float:
        raise TypeError('ail_array: arange() makes int arrays; write arange(n, ta.int32).astype(ta.%s)' % dt)
    if dt.is_bool:
        raise TypeError('ail_array: arange() makes int arrays, not bool_; write ta.arange(n, ta.int64).astype(ta.bool_)')
    return Array._of(dt, [_store(dt, k) for k in range(_length(n))])


def frombytes(data, dtype):
    """A new array whose storage is a copy of `data` (little-endian, bits kept as they are)."""
    dt = _dtype(dtype)
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError('ail_array: frombytes() needs bytes, not %s' % _type_name(data))
    if len(data) % dt.itemsize:
        raise ValueError('ail_array: byte length %d is not a multiple of %d (%s)' % (len(data), dt.itemsize, dt))
    if dt.is_bool:
        return Array._make(dt, bytearray(1 if b else 0 for b in data))     # a bool_ byte is 0 or 1
    return Array._make(dt, bytearray(data))


# ---- element-wise arithmetic -------------------------------------------------------------------------------------
_OPNAME = {'+': 'add', '-': 'sub', '*': 'mul', '//': 'floordiv', '%': 'mod', '/': 'truediv'}


def _operand(a, o, sym):
    """The other operand as a list of `a.dtype` values, or NotImplemented (design 3.6)."""
    dt = a._dt
    if isinstance(o, Array):
        if o._dt is not dt:
            raise TypeError('ail_array: %s %s %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)'
                            % (dt, sym, o._dt, o._dt, dt))
        if o._n != a._n:
            raise ValueError('ail_array: shapes differ: (%d,) and (%d,)' % (a._n, o._n))
        return o._values()
    if isinstance(o, (int, float)):
        if not dt.is_float and isinstance(o, float):
            raise TypeError('ail_array: %s %s float: write a.astype(ta.f64) (no implicit int-to-float)' % (dt, sym))
        return [_store(dt, o)] * a._n
    return NotImplemented


def _fdiv(x, y):
    if y == 0.0:
        if x != x or x == 0.0:
            return _NAN
        return math.copysign(_INF, math.copysign(1.0, x) * math.copysign(1.0, y))
    return x / y


_FOPS = {'+': lambda x, y: x + y, '-': lambda x, y: x - y, '*': lambda x, y: x * y, '/': _fdiv}


def _ifloordiv(x, y):
    if y == 0:
        raise ZeroDivisionError('integer division or modulo by zero')
    return x // y


def _imod(x, y):
    if y == 0:
        raise ZeroDivisionError('integer division or modulo by zero')
    return x % y


_IOPS = {'+': lambda x, y: x + y, '-': lambda x, y: x - y, '*': lambda x, y: x * y, '//': _ifloordiv, '%': _imod}


def _run(a, xs, step, name, into):
    """Apply `step(k)` in index order; int results are range-checked. With `into` (an in-place op), the elements
    before a failing index are written and the rest are not, as the loop `for i ...: a[i] op= b[i]` leaves them."""
    dt = a._dt
    out = []
    try:
        for k in range(len(xs)):
            v = step(k)
            if dt.is_float:
                v = _round(dt, v)
            elif v < dt.lo or v > dt.hi:
                raise OverflowError('%s %s overflow at index %d' % (dt.name, name, k))
            out.append(v)
    except BaseException:
        if into is not None and out:
            into._buf[:len(out) * dt.itemsize] = _pack(dt, out)
        raise
    if into is not None:
        into._buf[:] = _pack(dt, out)
        return into
    return Array._of(dt, out)


def _no_bool(dt, what):
    if dt.is_bool:
        raise TypeError('ail_array: %s on bool_ arrays is not defined; write a.astype(ta.int64) (or ta.logical_and/or/xor/not)'
                        % what)


def _binary(a, o, sym, reflected, into=None):
    dt = a._dt
    _no_bool(dt, sym)
    if dt.is_float and sym in ('//', '%'):
        raise TypeError('ail_array: %s is not defined for %s arrays; write a loop over a.tolist()' % (sym, dt))
    if not dt.is_float and sym == '/':
        raise TypeError('ail_array: / on %s arrays; write a.astype(ta.f64) / b.astype(ta.f64)' % dt)
    ys = _operand(a, o, sym)
    if ys is NotImplemented:
        return NotImplemented
    xs = a._values()
    if reflected:
        xs, ys = ys, xs
    op = (_FOPS if dt.is_float else _IOPS)[sym]
    return _run(a, xs, lambda k: op(xs[k], ys[k]), _OPNAME[sym], into)


def _unary(a, what):
    _no_bool(a._dt, what)
    xs = a._values()
    if what == 'neg':
        return _run(a, xs, lambda k: -xs[k], 'neg', None)
    return _run(a, xs, lambda k: abs(xs[k]), 'abs', None)


def _float_only(a, name):
    if not isinstance(a, Array):
        raise TypeError('ail_array.%s() needs an ail_array.Array, not %s' % (name, _type_name(a)))
    if not a._dt.is_float:
        raise TypeError('ail_array.%s() is defined for float arrays, not %s' % (name, a._dt))
    return a._values()


def _sqrt(x):
    if x != x or x < 0.0:
        return _NAN
    return math.sqrt(x)


def _exp(x):
    if x != x:
        return _NAN
    try:
        return math.exp(x)
    except OverflowError:
        return _INF


def _log(x):
    if x != x or x < 0.0:
        return _NAN
    if x == 0.0:
        return -_INF
    return math.log(x)


def _tanh(x):
    return _NAN if x != x else math.tanh(x)


def _mathfn(fn, name):
    def run(a):
        xs = _float_only(a, name)
        return Array._of(a._dt, [_round(a._dt, fn(x)) for x in xs])
    run.__name__ = name
    run.__doc__ = 'Element-wise %s: r_T(math.%s(x)) with IEEE results where math raises.' % (name, name)
    return run


sqrt = _mathfn(_sqrt, 'sqrt')
exp = _mathfn(_exp, 'exp')
log = _mathfn(_log, 'log')
tanh = _mathfn(_tanh, 'tanh')


def _less(x, y):
    """x < y with -0.0 below 0.0 (NaN handled by the callers)."""
    if x == y and x == 0:
        return math.copysign(1.0, x) < math.copysign(1.0, y)
    return x < y


def _pick(a, b, name, smaller):
    if not isinstance(a, Array):
        raise TypeError('ail_array.%s() needs an ail_array.Array first, not %s' % (name, _type_name(a)))
    ys = _operand(a, b, name)
    if ys is NotImplemented:
        raise TypeError('ail_array.%s(): unsupported operand %s' % (name, _type_name(b)))
    xs = a._values()
    out = []
    for x, y in zip(xs, ys):
        if x != x or y != y:
            out.append(_NAN)
        elif _less(y, x) == smaller:
            out.append(y)
        else:
            out.append(x)
    return Array._of(a._dt, out)


def minimum(a, b):
    """Element-wise minimum; NaN if either is NaN; -0.0 is below 0.0."""
    return _pick(a, b, 'minimum', True)


def maximum(a, b):
    """Element-wise maximum; NaN if either is NaN; 0.0 is above -0.0."""
    return _pick(a, b, 'maximum', False)


def clip(a, lo, hi):
    """minimum(maximum(a, lo), hi)."""
    return minimum(maximum(a, lo), hi)


def _int_pair(a, b, name):
    if not isinstance(a, Array):
        raise TypeError('ail_array.%s() needs an ail_array.Array first, not %s' % (name, _type_name(a)))
    if a._dt.is_float or a._dt.is_bool:
        raise TypeError('ail_array.%s() is defined for int arrays, not %s' % (name, a._dt))
    ys = _operand(a, b, name)
    if ys is NotImplemented:
        raise TypeError('ail_array.%s(): unsupported operand %s' % (name, _type_name(b)))
    return a._values(), ys


def _wrap(dt, v):
    m = 1 << dt.bits
    return ((v - dt.lo) % m) + dt.lo


def _sat(dt, v):
    return dt.lo if v < dt.lo else dt.hi if v > dt.hi else v


def _intfn(name, op, fix):
    def run(a, b):
        xs, ys = _int_pair(a, b, name)
        return Array._of(a._dt, [fix(a._dt, op(x, y)) for x, y in zip(xs, ys)])
    run.__name__ = name
    return run


wrapping_add = _intfn('wrapping_add', lambda x, y: x + y, _wrap)
wrapping_sub = _intfn('wrapping_sub', lambda x, y: x - y, _wrap)
wrapping_mul = _intfn('wrapping_mul', lambda x, y: x * y, _wrap)
saturating_add = _intfn('saturating_add', lambda x, y: x + y, _sat)
saturating_sub = _intfn('saturating_sub', lambda x, y: x - y, _sat)


# ---- casts --------------------------------------------------------------------------------------------------------
def _int_to_float(dt, v):
    """The float of the exact int `v` rounded once to `dt` (nearest-even; overflow is left to `_round`). `float(v)` first
    would round twice for |v| > 2^53 (int64 to f32 or f16)."""
    if dt is f64:
        return float(v)
    p = 24 if dt is f32 else 11
    m = builtins.abs(v)
    n = m.bit_length()
    if n > p:
        shift = n - p
        q, r = divmod(m, 1 << shift)
        half = 1 << (shift - 1)
        if r > half or (r == half and q & 1):
            q += 1
        m = q << shift
    x = float(m)
    return -x if v < 0 else x


def _astype(a, dt, rounding, overflow):
    if rounding not in ('trunc', 'nearest'):
        raise ValueError("ail_array: rounding must be 'trunc' or 'nearest', not %r" % (rounding,))
    if overflow not in ('raise', 'saturate', 'wrap'):
        raise ValueError("ail_array: overflow must be 'raise', 'saturate' or 'wrap', not %r" % (overflow,))
    src = a._dt
    xs = a._values()
    if dt.is_bool:
        return Array._of(dt, [x != 0 for x in xs])                 # nonzero, so NaN is True and -0.0 is False
    if dt.is_float:
        if src.is_float:
            return Array._of(dt, [_round(dt, float(x)) for x in xs])
        return Array._of(dt, [_round(dt, _int_to_float(dt, int(x))) for x in xs])     # one rounding, also for int64
    if src.is_float and overflow == 'wrap':
        raise ValueError("ail_array: overflow='wrap' is for int-to-int casts; use 'raise' or 'saturate'")
    out = []
    for k, x in enumerate(xs):
        if src.is_float:
            if x != x:
                if overflow == 'saturate':
                    out.append(0)
                    continue
                raise ValueError('cannot convert float NaN to integer')
            if x in (_INF, -_INF):
                if overflow == 'saturate':
                    out.append(dt.hi if x > 0 else dt.lo)
                    continue
                raise OverflowError('cannot convert float infinity to integer')
            v = int(x) if rounding == 'trunc' else round(x)
        else:
            v = int(x)
        if v < dt.lo or v > dt.hi:
            if overflow == 'saturate':
                v = _sat(dt, v)
            elif overflow == 'wrap':
                v = _wrap(dt, v)
            else:
                raise OverflowError('%s cast overflow at index %d' % (dt.name, k))
        out.append(v)
    return Array._of(dt, out)


# ---- reductions ---------------------------------------------------------------------------------------------------
def _acc(a, acc, name):
    if acc is None:
        return f32 if a._dt is f16 else a._dt
    acc = _dtype(acc)
    if not a._dt.is_float:
        raise ValueError('ail_array.%s(): acc= is for float arrays; %s sums are exact' % (name, a._dt))
    if not acc.is_float or _WIDTH[acc] < _WIDTH[a._dt]:
        raise ValueError('ail_array.%s(): acc=%s would narrow %s' % (name, acc, a._dt))
    return acc


def _order(order, name):
    if order is not None and order != 'any':
        raise ValueError("ail_array.%s(): order must be 'any' or omitted, not %r" % (name, order))


def _block_sum(A, xs, start, stop):
    """One block: 16 lanes from -0.0, element k to lane k % 16, then the 8-4-2-1 tree."""
    lanes = [-0.0] * LANES
    for k in range(start, stop):
        lane = (k - start) % LANES
        lanes[lane] = _round(A, lanes[lane] + xs[k])
    w = LANES // 2
    while w:
        for i in range(w):
            lanes[i] = _round(A, lanes[i] + lanes[i + w])
        w //= 2
    return lanes[0]


def _tree(A, blocks, lo, hi):
    if hi - lo == 1:
        return blocks[lo]
    p = 1
    while p * 2 < hi - lo:
        p *= 2
    return _round(A, _tree(A, blocks, lo, lo + p) + _tree(A, blocks, lo + p, hi))


def _fixed_sum(A, xs):
    """The fixed order of design 3.5 over values already in `A` (Python floats)."""
    n = len(xs)
    if n == 0:
        return 0.0
    blocks = [_block_sum(A, xs, s, builtins.min(s + BLOCK, n)) for s in range(0, n, BLOCK)]
    r = _tree(A, blocks, 0, len(blocks))
    return _NAN if r != r else r


def sum(a, acc=None, order=None):
    """The module's sum: exact Python int for int arrays; the fixed blocked order for floats (a Python float)."""
    if not isinstance(a, Array):
        raise TypeError('ail_array.sum() needs an ail_array.Array, not %s' % _type_name(a))
    A = _acc(a, acc, 'sum')
    _order(order, 'sum')
    xs = a._values()
    if not a._dt.is_float:
        total = 0
        for x in xs:
            total += x
        if a._dt is int64 and not -(1 << 63) <= total < (1 << 63):
            raise OverflowError('int64 sum overflow')
        return total
    return _fixed_sum(A, xs)


def dot(a, b, acc=None, order=None):
    """sum(a * b) bit for bit: products rounded to the accumulator dtype, then the fixed order; ints are exact."""
    if not isinstance(a, Array) or not isinstance(b, Array):
        raise TypeError('ail_array.dot() needs two ail_array.Array values')
    if a._dt.is_bool:
        raise TypeError('ail_array.dot() is defined for numeric arrays, not bool_')
    ys = _operand(a, b, 'dot')
    A = _acc(a, acc, 'dot')
    _order(order, 'dot')
    xs = a._values()
    if not a._dt.is_float:
        total = 0
        for x, y in zip(xs, ys):
            total += x * y
        if a._dt is int64 and not -(1 << 63) <= total < (1 << 63):
            raise OverflowError('int64 dot overflow')
        return total
    return _fixed_sum(A, [_round(A, x * y) for x, y in zip(xs, ys)])


def _extreme(a, name, smaller):
    if not isinstance(a, Array):
        raise TypeError('ail_array.%s() needs an ail_array.Array, not %s' % (name, _type_name(a)))
    xs = a._values()
    if not xs:
        raise ValueError('%s() iterable argument is empty' % name)
    best = 0
    for k, x in enumerate(xs):
        if x != x:
            return k, _NAN
        if k and (_less(x, xs[best]) if smaller else _less(xs[best], x)):
            best = k
    return best, xs[best]


def min(a, order=None):
    """Smallest element; NaN if any element is NaN; -0.0 is below 0.0."""
    if order is not None:
        raise ValueError("ta.min has no inexact form; drop order='any'")
    return _extreme(a, 'min', True)[1]


def max(a, order=None):
    """Largest element; NaN if any element is NaN; 0.0 is above -0.0."""
    if order is not None:
        raise ValueError("ta.max has no inexact form; drop order='any'")
    return _extreme(a, 'max', False)[1]


def argmin(a):
    """Lowest index of the smallest element (the first NaN if there is one)."""
    return _extreme(a, 'argmin', True)[0]


def argmax(a):
    """Lowest index of the largest element (the first NaN if there is one)."""
    return _extreme(a, 'argmax', False)[0]


# ---- stage T3b: wrapping forms the torch layer calls --------------------------------------------------------------
def _int_array(a, name):
    if not isinstance(a, Array):
        raise TypeError('ail_array.%s() needs an ail_array.Array, not %s' % (name, _type_name(a)))
    if a._dt.is_float or a._dt.is_bool:
        raise TypeError('ail_array.%s() is defined for int arrays, not %s' % (name, a._dt))
    return a._values()


def wrapping_neg(a):
    """Two's-complement negation: the minimum value stays the minimum."""
    return Array._of(a._dt, [_wrap(a._dt, -x) for x in _int_array(a, 'wrapping_neg')])


def wrapping_abs(a):
    """abs with the minimum value staying the minimum."""
    return Array._of(a._dt, [_wrap(a._dt, builtins.abs(x)) for x in _int_array(a, 'wrapping_abs')])


def wrapping_floordiv(a, b):
    """Python's floor division; only `min // -1` differs from `//` (it wraps to min instead of raising). A zero divisor
    raises ZeroDivisionError as `//` does."""
    xs, ys = _int_pair(a, b, 'wrapping_floordiv')
    return Array._of(a._dt, [_wrap(a._dt, _ifloordiv(x, y)) for x, y in zip(xs, ys)])


def _int64_only(a, name):
    if not isinstance(a, Array):
        raise TypeError('ail_array.%s() needs an ail_array.Array, not %s' % (name, _type_name(a)))
    if a._dt is not int64:
        raise TypeError('ail_array.%s() is for int64 arrays, not %s (int8/int32 sums are exact and cannot leave int64)'
                        % (name, a._dt))


def wrapping_sum(a):
    """The sum of an int64 array modulo 2^64, as a Python int in the int64 range (the order does not matter)."""
    _int64_only(a, 'wrapping_sum')
    return _wrap(int64, builtins.sum(a._values()))


def wrapping_dot(a, b):
    """sum(a * b) modulo 2^64 for int64 arrays."""
    _int64_only(a, 'wrapping_dot')
    ys = _operand(a, b, 'wrapping_dot')
    return _wrap(int64, builtins.sum(x * y for x, y in zip(a._values(), ys)))


# ---- comparisons, logic, where, any/all ---------------------------------------------------------------------------
def _compare(a, b, name, op):
    if not isinstance(a, Array):
        raise TypeError('ail_array.%s() needs an ail_array.Array first, not %s' % (name, _type_name(a)))
    ys = _operand(a, b, name)
    if ys is NotImplemented:
        raise TypeError('ail_array.%s(): unsupported operand %s' % (name, _type_name(b)))
    return Array._of(bool_, [op(x, y) for x, y in zip(a._values(), ys)])


def eq(a, b):
    """Element-wise a == b as a bool_ array (IEEE: NaN is unequal to everything, -0.0 == 0.0)."""
    return _compare(a, b, 'eq', lambda x, y: x == y)


def ne(a, b):
    return _compare(a, b, 'ne', lambda x, y: x != y)


def lt(a, b):
    return _compare(a, b, 'lt', lambda x, y: x < y)


def le(a, b):
    return _compare(a, b, 'le', lambda x, y: x <= y)


def gt(a, b):
    return _compare(a, b, 'gt', lambda x, y: x > y)


def ge(a, b):
    return _compare(a, b, 'ge', lambda x, y: x >= y)


def _logic(a, b, name, op):
    if not isinstance(a, Array) or not a._dt.is_bool:
        raise TypeError('ail_array.%s() needs bool_ arrays; write ta.ne(a, 0) or a.astype(ta.bool_)' % name)
    ys = _operand(a, b, name)
    if ys is NotImplemented:
        raise TypeError('ail_array.%s(): unsupported operand %s' % (name, _type_name(b)))
    return Array._of(bool_, [op(x, y) for x, y in zip(a._values(), ys)])


def logical_and(a, b):
    return _logic(a, b, 'logical_and', lambda x, y: x and y)


def logical_or(a, b):
    return _logic(a, b, 'logical_or', lambda x, y: x or y)


def logical_xor(a, b):
    return _logic(a, b, 'logical_xor', lambda x, y: x != y)


def logical_not(a):
    if not isinstance(a, Array) or not a._dt.is_bool:
        raise TypeError('ail_array.logical_not() needs a bool_ array; write ta.eq(a, 0) or a.astype(ta.bool_)')
    return Array._of(bool_, [not x for x in a._values()])


def where(mask, a, b):
    """mask ? a : b element by element. `a` and `b` are arrays of one dtype, or one is a Python number (stored to the
    other's dtype); the result has that dtype and mask's length."""
    if not isinstance(mask, Array) or not mask._dt.is_bool:
        raise TypeError('ail_array.where() needs a bool_ array as the mask, not %s' % (
            mask._dt if isinstance(mask, Array) else _type_name(mask)))
    if isinstance(a, Array):
        ys = _operand(a, b, 'where')
        if ys is NotImplemented:
            raise TypeError('ail_array.where(): unsupported operand %s' % _type_name(b))
        dt, xs = a._dt, a._values()
    elif isinstance(b, Array):
        dt, ys = b._dt, b._values()
        xs = _operand(b, a, 'where')
        if xs is NotImplemented:
            raise TypeError('ail_array.where(): unsupported operand %s' % _type_name(a))
    else:
        raise TypeError('ail_array.where() needs an ail_array.Array for a or b')
    if len(xs) != mask._n:
        raise ValueError('ail_array: shapes differ: (%d,) and (%d,)' % (mask._n, len(xs)))
    return Array._of(dt, [x if m else y for m, x, y in zip(mask._values(), xs, ys)])


def any(a):
    """True when some element is nonzero (NaN counts as nonzero); False for the empty array."""
    if not isinstance(a, Array):
        raise TypeError('ail_array.any() needs an ail_array.Array, not %s' % _type_name(a))
    return builtins.any(x != 0 for x in a._values())


def all(a):
    """True when every element is nonzero (NaN counts as nonzero); True for the empty array."""
    if not isinstance(a, Array):
        raise TypeError('ail_array.all() needs an ail_array.Array, not %s' % _type_name(a))
    return builtins.all(x != 0 for x in a._values())


# ---- gather and scatter: moves only, so exact ------------------------------------------------------------------------
def _indices(idx, name):
    if not isinstance(idx, Array):
        raise TypeError('ail_array.%s(): indices must be an ail_array.Array, not %s' % (name, _type_name(idx)))
    if idx._dt.is_float or idx._dt.is_bool:
        raise TypeError('ail_array.%s(): indices must be an int array, not %s' % (name, idx._dt))
    return idx._values()


def _need_array(a, name):
    if not isinstance(a, Array):
        raise TypeError('ail_array.%s() needs an ail_array.Array, not %s' % (name, _type_name(a)))


def _position(i, n):
    """Index `i` (negative counts from the end) of an array of n elements, or the IndexError of PyTorch's x[idx]."""
    k = i + n if i < 0 else i
    if k < 0 or k >= n:
        raise IndexError('index %d is out of bounds for dimension 0 with size %d' % (i, n))
    return k


def take(a, idx):
    """The elements at the positions in the int array `idx` (negative counts from the end), as a new array of a's dtype.
    The bytes are copied, so every bit (NaN payloads too) is kept."""
    _need_array(a, 'take')
    ks = [_position(i, a._n) for i in _indices(idx, 'take')]
    size = a._dt.itemsize
    out = bytearray()
    for k in ks:
        out += a._buf[k * size:(k + 1) * size]
    return Array._make(a._dt, out)


def put(a, idx, src, accumulate=False, overflow='raise'):
    """a[idx[j]] = src[j] for j in order (the last write to a position wins), in place. `src` is an array of a's dtype
    and idx's length, or one Python number for every position. The dtype and the length are checked first; then the
    writes happen in order and an index outside the array raises at its position with the elements before it already
    written (PyTorch's index_put_ does the same). With accumulate=True the element becomes a[idx[j]] + src[j]: floats
    round per add, ints raise OverflowError ('int64 add overflow at index j') or, with overflow='wrap', wrap. Returns
    None."""
    _need_array(a, 'put')
    ints = _indices(idx, 'put')
    dt = a._dt
    if overflow not in ('raise', 'wrap'):
        raise ValueError("ail_array.put(): overflow must be 'raise' or 'wrap', not %r" % (overflow,))
    if isinstance(src, Array):
        if src._dt is not dt:
            raise TypeError('ail_array: %s put %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)'
                            % (dt, src._dt, src._dt, dt))
        if src._n != len(ints):
            raise ValueError('ail_array.put(): src has %d elements but there are %d indices' % (src._n, len(ints)))
        vs = src._values()
    else:
        vs = [_store(dt, src)] * len(ints)
    if accumulate:
        _no_bool(dt, 'put(accumulate=True)')
        if dt.is_float and overflow == 'wrap':
            raise ValueError("ail_array.put(): overflow='wrap' is for int arrays")
    size = dt.itemsize
    for j, (i, v) in enumerate(zip(ints, vs)):
        k = _position(i, a._n)
        if accumulate:
            cur = _ONE_READ[dt].unpack_from(a._buf, k * size)[0]
            if dt.is_float:
                v = _round(dt, cur + v)
            else:
                v = cur + v
                if v < dt.lo or v > dt.hi:
                    if overflow == 'wrap':
                        v = _wrap(dt, v)
                    else:
                        raise OverflowError('%s add overflow at index %d' % (dt.name, j))
        a._buf[k * size:(k + 1) * size] = _pack(dt, [v])


def _shape_args(offset, shape, strides, name):
    if isinstance(offset, builtins.bool) or not isinstance(offset, int):
        raise TypeError('ail_array.%s(): offset must be an int, not %s' % (name, _type_name(offset)))
    for what, seq in (('shape', shape), ('strides', strides)):
        if not isinstance(seq, (list, tuple)):
            raise TypeError('ail_array.%s(): %s must be a list or tuple of ints, not %s' % (name, what, _type_name(seq)))
        for d in seq:
            if isinstance(d, builtins.bool) or not isinstance(d, int):
                raise TypeError('ail_array.%s(): %s must hold ints, not %s' % (name, what, _type_name(d)))
    if len(shape) != len(strides):
        raise ValueError('ail_array.%s(): shape and strides differ in length (%d and %d)' % (name, len(shape), len(strides)))
    for d in shape:
        if d < 0:
            raise ValueError('ail_array.%s(): negative size %d in shape' % (name, d))
    total = 1
    for d in shape:
        total *= d
    return total


def _positions(n, offset, shape, strides, name, verb):
    """The array positions of the elements of a strided view, in C order of the logical index; IndexError at the
    first one outside 0..n-1 (strides may be zero or negative)."""
    total = _shape_args(offset, shape, strides, name)
    out = []
    if total == 0:
        return out
    idx = [0] * len(shape)
    p = offset
    for e in range(total):
        if p < 0 or p >= n:
            raise IndexError('ail_array.%s(): element %d %s index %d, outside the array of %d elements'
                             % (name, e, verb, p, n))
        out.append(p)
        d = len(shape) - 1
        while d >= 0:
            idx[d] += 1
            p += strides[d]
            if idx[d] < shape[d]:
                break
            p -= shape[d] * strides[d]
            idx[d] = 0
            d -= 1
    return out


def gather_strided(a, offset, shape, strides):
    """A new 1-D array of prod(shape) elements: element (i0, i1, ...) in C order is a[offset + i0*strides[0] + ...].
    Strides count elements; zero strides repeat (broadcast). Bytes are copied, so every bit is kept."""
    _need_array(a, 'gather_strided')
    ps = _positions(a._n, offset, shape, strides, 'gather_strided', 'reads')
    size = a._dt.itemsize
    out = bytearray()
    for p in ps:
        out += a._buf[p * size:(p + 1) * size]
    return Array._make(a._dt, out)


def scatter_strided(dst, offset, shape, strides, src):
    """dst[offset + i0*strides[0] + ...] = src[e] for the elements e in C order, in place (a position written twice
    keeps the later element). `src` is an array of dst's dtype with prod(shape) elements, or one Python number.
    Every position is checked before anything is written. Returns None."""
    _need_array(dst, 'scatter_strided')
    ps = _positions(dst._n, offset, shape, strides, 'scatter_strided', 'writes')
    dt = dst._dt
    size = dt.itemsize
    if isinstance(src, Array):
        if src._dt is not dt:
            raise TypeError('ail_array: %s scatter %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)'
                            % (dt, src._dt, src._dt, dt))
        if src._n != len(ps):
            raise ValueError('ail_array.scatter_strided(): src has %d elements but the shape has %d' % (src._n, len(ps)))
        data = bytes(src._buf)
        for e, p in enumerate(ps):
            dst._buf[p * size:(p + 1) * size] = data[e * size:(e + 1) * size]
        return
    one = _pack(dt, [_store(dt, src)])
    for p in ps:
        dst._buf[p * size:(p + 1) * size] = one


# ---- segmented reductions --------------------------------------------------------------------------------------------
def _segments(a, offsets, name):
    """[(start, stop)] of the segments a[offsets[k]:offsets[k+1]]; offsets rise from >= 0 to <= len(a)."""
    _need_array(a, name)
    os_ = _indices(offsets, name)
    if not os_:
        raise ValueError('ail_array.%s(): offsets needs at least one element' % name)
    for k, o in enumerate(os_):
        if o < 0 or o > a._n or (k and o < os_[k - 1]):
            raise ValueError('ail_array.%s(): offsets[%d] = %d is out of order or outside 0..%d' % (name, k, o, a._n))
    return list(zip(os_[:-1], os_[1:]))


def _exact_segment_sums(a, offsets, name, wrap):
    segs = _segments(a, offsets, name)
    xs = a._values()
    out = []
    for k, (lo, hi) in enumerate(segs):
        total = 0
        for x in xs[lo:hi]:
            total += x
        if not -(1 << 63) <= total < (1 << 63):
            if wrap:
                total = _wrap(int64, total)
            else:
                raise OverflowError('int64 segment_sum overflow at segment %d' % k)
        out.append(total)
    return Array._of(int64, out)


def segment_sum(a, offsets):
    """One sum per segment a[offsets[k]:offsets[k+1]]. Floats: design 3.5's order inside each segment, rounded to a's
    dtype (an empty segment gives +0.0). Ints and bool_: exact, as an int64 array, OverflowError if one leaves int64."""
    if isinstance(a, Array) and not a._dt.is_float:
        return _exact_segment_sums(a, offsets, 'segment_sum', False)
    segs = _segments(a, offsets, 'segment_sum')
    xs, dt = a._values(), a._dt
    A = f32 if dt is f16 else dt
    return Array._of(dt, [_round(dt, _fixed_sum(A, xs[lo:hi])) for lo, hi in segs])


def wrapping_segment_sum(a, offsets):
    """segment_sum of int arrays with each sum taken modulo 2^64 (the int64 result wraps instead of raising)."""
    if isinstance(a, Array) and a._dt.is_float:
        raise TypeError('ail_array.wrapping_segment_sum() is defined for int arrays, not %s' % a._dt)
    return _exact_segment_sums(a, offsets, 'wrapping_segment_sum', True)


def _segment_extreme(a, offsets, name, smaller, want_index):
    segs = _segments(a, offsets, name)
    xs = a._values()
    out = []
    for k, (lo, hi) in enumerate(segs):
        if lo == hi:
            raise ValueError('ail_array.%s(): segment %d is empty' % (name, k))
        best = lo
        found = None
        for j in range(lo, hi):
            x = xs[j]
            if x != x:
                found = j
                break
            if j > lo and (_less(x, xs[best]) if smaller else _less(xs[best], x)):
                best = j
        j = best if found is None else found
        out.append(j - lo if want_index else (_NAN if found is not None else xs[j]))
    return Array._of(int64 if want_index else a._dt, out)


def segment_min(a, offsets):
    """The smallest element of each segment (NaN if the segment has one; -0.0 < 0.0); ValueError on an empty segment."""
    return _segment_extreme(a, offsets, 'segment_min', True, False)


def segment_max(a, offsets):
    return _segment_extreme(a, offsets, 'segment_max', False, False)


def segment_argmin(a, offsets):
    """Per segment, the lowest index inside the segment of its smallest element (the first NaN), as an int64 array."""
    return _segment_extreme(a, offsets, 'segment_argmin', True, True)


def segment_argmax(a, offsets):
    return _segment_extreme(a, offsets, 'segment_argmax', False, True)


# ---- flat matrix product ---------------------------------------------------------------------------------------------
def mm(a, b, m, k, n):
    """The (m x k) by (k x n) product of two flat row-major float arrays (f32 or f64) as a flat m*n array. Element
    (i, j) is dot(a[i*k:(i+1)*k], b[j::n]) bit for bit: the products rounded to the dtype, then design 3.5's order along
    k (K = 0 gives +0.0). It is the order the 2-D matmul of TYPED_ARRAY 3.7 defines, for f32 as for f64."""
    if not isinstance(a, Array) or not isinstance(b, Array):
        raise TypeError('ail_array.mm() needs two ail_array.Array values')
    dt = a._dt
    if b._dt is not dt:
        raise TypeError('ail_array: %s mm %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)'
                        % (dt, b._dt, b._dt, dt))
    if dt is not f32 and dt is not f64:
        raise TypeError('ail_array.mm(): only f32 and f64 arrays are built, not %s' % dt)
    for what, v in (('m', m), ('k', k), ('n', n)):
        if isinstance(v, builtins.bool) or not isinstance(v, int):
            raise TypeError('ail_array.mm(): %s must be an int, not %s' % (what, _type_name(v)))
        if v < 0:
            raise ValueError('ail_array.mm(): negative size %s = %d' % (what, v))
    if a._n != m * k:
        raise ValueError('ail_array.mm(): a has %d elements, expected %d (%d x %d)' % (a._n, m * k, m, k))
    if b._n != k * n:
        raise ValueError('ail_array.mm(): b has %d elements, expected %d (%d x %d)' % (b._n, k * n, k, n))
    xs, ys = a._values(), b._values()
    out = []
    for i in range(m):
        row = xs[i * k:(i + 1) * k]
        for j in range(n):
            out.append(_fixed_sum(dt, [_round(dt, row[t] * ys[t * n + j]) for t in range(k)]))
    return Array._of(dt, out)


# ---- dtype promotion (PyTorch's rules, for the torch layer) ----------------------------------------------------------
def promote_types(a, b):
    """The dtype PyTorch gives an operation on two tensors of dtypes a and b: bool < int < float; the wider one
    inside a category; any float wins over any int (int64 with f16 is f16)."""
    _dtype(a), _dtype(b)
    if a.is_float or b.is_float:
        fl = [d for d in (a, b) if d.is_float]
        return fl[0] if len(fl) == 1 or _WIDTH[fl[0]] >= _WIDTH[fl[1]] else fl[1]
    if a.is_bool:
        return b
    if b.is_bool:
        return a
    return a if a.bits >= b.bits else b


def promote_scalar(dtype, scalar, default_float=None):
    """The dtype of `tensor(dtype) op scalar` for a Python scalar (PyTorch: a scalar only raises the category):
    a bool scalar keeps dtype; an int scalar turns bool into int64; a float scalar turns bool and ints into the
    default float (f32 unless `default_float` says otherwise)."""
    dt = _dtype(dtype)
    if isinstance(scalar, builtins.bool):
        return dt
    if isinstance(scalar, int):
        return int64 if dt.is_bool else dt
    if isinstance(scalar, float):
        return dt if dt.is_float else (f32 if default_float is None else _dtype(default_float))
    raise TypeError('ail_array.promote_scalar(): scalar must be a bool, int or float, not %s' % _type_name(scalar))
