"""Typed arrays with declared element types: the pure-Python reference of `ail_array` (stage T1).

The meaning of every operation is defined in docs/design/TYPED_ARRAY.md. This file implements exactly that meaning on
plain CPython 3.12 (standard library only, no numpy), and it is the oracle AIL's native lowering is compared with:
a program that imports `ail_array` prints, under CPython with this file beside it, what its AIL build must print.

    import ail_array as ta
    a = ta.array([1.0, 2.5, -0.0], ta.f32)
    y = (a * 2.0 + a) / 3.0          # every op rounded to f32, nothing fused
    print(ta.sum(y), y.tobytes().hex())

Dtypes: f64, f32, f16 (IEEE binary64/32/16) and int8, int32. Arrays are 1-D, or 2-D (row-major, `zeros((r, c), dt)`,
`array([[...], [...]], dt)`); `ta.matmul(A, B)` multiplies two 2-D f64 arrays (stage T6, section 3.7 of the design note).

How the bits are made (design sections 3 and 4):
* Float ops compute in binary64 (Python floats, correctly rounded) and round once to the dtype with `struct`. For
  `+ - * /` and sqrt that equals one correct rounding in the dtype (53 >= 2p + 2 for p = 24 and p = 11).
* Overflow goes to +-inf (`struct` raises instead, so the overflow is caught); division by zero is IEEE; subnormals
  are kept; every NaN an operation produces is the canonical positive quiet NaN. Bits that come in through
  `frombytes` are stored unchanged until an operation touches them.
* int8/int32 `+ - * // %`, unary `-` and `abs` are exact and raise OverflowError at the first index whose result does
  not fit; `wrapping_*` and `saturating_*` are the explicit alternatives.
* `sum` and `dot` of floats use one fixed order: blocks of 1024 elements, 16 lanes per block starting at -0.0, an
  8-4-2-1 tree over the lanes, and a power-of-two tree over the blocks.
* `matmul(A, B)[i, j]` is `dot(A[i], B[:, j])` bit for bit: the same order along k for every output element.
"""
import builtins
import math
import struct

__all__ = ['DType', 'Array', 'Matrix', 'f64', 'f32', 'f16', 'int8', 'int32', 'array', 'zeros', 'full', 'arange', 'frombytes',
           'sqrt', 'exp', 'log', 'tanh', 'minimum', 'maximum', 'clip', 'wrapping_add', 'wrapping_sub',
           'wrapping_mul', 'saturating_add', 'saturating_sub', 'sum', 'dot', 'matmul', 'min', 'max', 'argmin', 'argmax']

BLOCK = 1024
LANES = 16


class DType:
    """One of the five element types. Compare with `is`; `repr` is the name."""
    __slots__ = ('name', 'itemsize', 'code', 'is_float', 'lo', 'hi', 'bits')

    def __init__(self, name, itemsize, code, is_float, bits):
        self.name, self.itemsize, self.code, self.is_float, self.bits = name, itemsize, code, is_float, bits
        self.lo = None if is_float else -(1 << (bits - 1))
        self.hi = None if is_float else (1 << (bits - 1)) - 1

    def __repr__(self):
        return self.name

    def __reduce__(self):
        return self.name


f64 = DType('f64', 8, 'd', True, 64)
f32 = DType('f32', 4, 'f', True, 32)
f16 = DType('f16', 2, 'e', True, 16)
int8 = DType('int8', 1, 'b', False, 8)
int32 = DType('int32', 4, 'i', False, 32)
_DTYPES = (f64, f32, f16, int8, int32)
_WIDTH = {f16: 1, f32: 2, f64: 3}

# The canonical quiet NaN, sign bit clear (binary64 7ff8000000000000; packs to f32 7fc00000 and f16 7e00).
_NAN = struct.unpack('<d', bytes.fromhex('000000000000f87f'))[0]
_INF = float('inf')
_ONE = {code: struct.Struct('<' + code) for code in 'dfe'}


def _dtype(dt):
    if not isinstance(dt, DType):
        raise TypeError('ail_array: dtype must be one of f64, f32, f16, int8, int32, not %s' % type(dt).__name__)
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


class _Alias2:
    __slots__ = ('dtype',)

    def __init__(self, dtype):
        self.dtype = dtype

    def __repr__(self):
        return 'Matrix[%s]' % self.dtype


class Matrix:
    """Annotation only: `ta.Matrix[ta.f64]` names a 2-D array (the values are `Array`)."""
    __slots__ = ()

    def __class_getitem__(cls, dtype):
        return _Alias2(dtype)


class Array:
    """A fixed-size array of one dtype, 1-D or 2-D (row-major), stored little-endian in a bytearray (the native layout).
    `_sh` is None for 1-D and (rows, cols) for 2-D."""
    __slots__ = ('_dt', '_n', '_buf', '_sh')
    __hash__ = None

    def __class_getitem__(cls, dtype):
        return _Alias(dtype)

    # ---- construction helpers -------------------------------------------------------------------------------------
    @classmethod
    def _make(cls, dt, buf, sh=None):
        a = object.__new__(cls)
        a._dt, a._n, a._buf, a._sh = dt, len(buf) // dt.itemsize, buf, sh
        return a

    @classmethod
    def _of(cls, dt, values, sh=None):
        return cls._make(dt, _pack(dt, values), sh)

    def _values(self):
        return list(struct.unpack_from('<%d%s' % (self._n, self._dt.code), self._buf))

    # ---- size -----------------------------------------------------------------------------------------------------
    @property
    def dtype(self):
        return self._dt

    @property
    def shape(self):
        return (self._n,) if self._sh is None else self._sh

    @property
    def T(self):
        if self._sh is None:
            raise ValueError('ail_array: .T needs a 2-D array, not a 1-D one')
        r, c = self._sh
        xs = self._values()
        return Array._of(self._dt, [xs[i * c + j] for j in range(c) for i in range(r)], (c, r))

    def __len__(self):
        return self._n if self._sh is None else self._sh[0]

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

    def _index2(self, i, n):
        if isinstance(i, int):
            i = int(i)
        elif hasattr(type(i), '__index__'):
            i = type(i).__index__(i)
        else:
            raise TypeError('array indices must be integers')
        if i < 0:
            i += n
        if i < 0 or i >= n:
            raise IndexError('array index out of range')
        return i

    def __getitem__(self, i):
        size = self._dt.itemsize
        if self._sh is not None:
            r, c = self._sh
            if isinstance(i, tuple):
                if len(i) != 2 or isinstance(i[0], slice) or isinstance(i[1], slice):
                    raise TypeError('ail_array: a 2-D array takes M[i, j] (two ints), M[i] or M[a:b]')
                p = self._index2(i[0], r)
                q = self._index2(i[1], c)
                return _ONE_READ[self._dt].unpack_from(self._buf, (p * c + q) * size)[0]
            if isinstance(i, slice):
                out = bytearray()
                ks = range(*i.indices(r))
                for k in ks:
                    out += self._buf[k * c * size:(k + 1) * c * size]
                return Array._make(self._dt, out, (len(ks), c))
            p = self._index2(i, r)
            return Array._make(self._dt, bytearray(self._buf[p * c * size:(p + 1) * c * size]))
        if isinstance(i, tuple):
            raise TypeError('ail_array: a 1-D array takes one index')
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
        if self._sh is not None:
            r, c = self._sh
            if isinstance(i, tuple):
                if len(i) != 2 or isinstance(i[0], slice) or isinstance(i[1], slice):
                    raise TypeError('ail_array: a 2-D array takes M[i, j] (two ints), M[i] or M[a:b]')
                p = self._index2(i[0], r)
                q = self._index2(i[1], c)
                v = _store(self._dt, x)
                k = p * c + q
                self._buf[k * size:(k + 1) * size] = _pack(self._dt, [v])
                return
            if isinstance(i, slice):
                raise TypeError('ail_array: slice assignment into a 2-D array is not built; assign one row at a time')
            p = self._index2(i, r)
            if not isinstance(x, Array):
                raise TypeError('ail_array: can only assign an ail_array.Array to a row, not %s' % _type_name(x))
            if x._dt is not self._dt:
                raise TypeError('ail_array: row assignment: dtypes differ (%s and %s)' % (self._dt, x._dt))
            if x._sh is not None or x._n != c:
                raise ValueError('ail_array: row assignment needs a 1-D array of %d elements, not shape %s' % (c, x.shape))
            self._buf[p * c * size:(p + 1) * c * size] = x._buf
            return
        if isinstance(i, tuple):
            raise TypeError('ail_array: a 1-D array takes one index')
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
        for k in range(len(self)):
            yield self[k]

    def __contains__(self, x):
        return any(v == x for v in self._values())

    # ---- conversion -----------------------------------------------------------------------------------------------
    def tolist(self):
        xs = self._values()
        if self._sh is None:
            return xs
        r, c = self._sh
        return [xs[i * c:(i + 1) * c] for i in range(r)]

    def tobytes(self):
        return bytes(self._buf)

    def copy(self):
        return Array._make(self._dt, bytearray(self._buf), self._sh)

    def astype(self, dtype, rounding='trunc', overflow='raise'):
        return _astype(self, _dtype(dtype), rounding, overflow)

    # ---- comparison and text --------------------------------------------------------------------------------------
    def __eq__(self, other):
        if not isinstance(other, Array):
            return NotImplemented
        return self._dt is other._dt and self.shape == other.shape and self._values() == other._values()

    def __ne__(self, other):
        r = self.__eq__(other)
        return r if r is NotImplemented else not r

    def __repr__(self):
        if self._sh is not None:
            return 'array([%s], %s)' % (', '.join('[%s]' % ', '.join(repr(v) for v in row) for row in self.tolist()),
                                        self._dt.name)
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
def _dim(n):
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError('ail_array: a length must be an int, not %s' % _type_name(n))
    if n < 0:
        raise ValueError('ail_array: negative length %d' % n)
    return n


def _shape(shape):
    """(element count, None) for a length or a 1-tuple; (rows * cols, (rows, cols)) for a 2-tuple."""
    if isinstance(shape, tuple):
        if len(shape) == 1:
            shape = shape[0]
        elif len(shape) == 2:
            r = _dim(shape[0])
            c = _dim(shape[1])
            return r * c, (r, c)
        else:
            raise ValueError('ail_array has 1-D and 2-D arrays; shape %r' % (shape,))
    return _dim(shape), None


def _length(shape):
    return _shape(shape)[0]


def array(values, dtype):
    """A new array of `dtype` from an iterable of int/float/bool; every value goes through the store rule."""
    dt = _dtype(dtype)
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError('ail_array: array() needs an iterable of numbers, not %s' % _type_name(values))
    if isinstance(values, (list, tuple)) and values and all(isinstance(row, (list, tuple)) for row in values):
        c = len(values[0])
        for row in values:
            if len(row) != c:
                raise ValueError('ail_array: array(): rows differ in length (%d and %d)' % (c, len(row)))
        return Array._of(dt, [_store(dt, x) for row in values for x in row], (len(values), c))
    return Array._of(dt, [_store(dt, x) for x in values])


def zeros(shape, dtype):
    dt = _dtype(dtype)
    n, sh = _shape(shape)
    return Array._make(dt, bytearray(n * dt.itemsize), sh)


def full(shape, value, dtype):
    dt = _dtype(dtype)
    n, sh = _shape(shape)
    return Array._of(dt, [_store(dt, value)] * n, sh)


def arange(n, dtype):
    dt = _dtype(dtype)
    if dt.is_float:
        raise TypeError('ail_array: arange() makes int arrays; write arange(n, ta.int32).astype(ta.%s)' % dt)
    return Array._of(dt, [_store(dt, k) for k in range(_length(n))])


def frombytes(data, dtype):
    """A new array whose storage is a copy of `data` (little-endian, bits kept as they are)."""
    dt = _dtype(dtype)
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError('ail_array: frombytes() needs bytes, not %s' % _type_name(data))
    if len(data) % dt.itemsize:
        raise ValueError('ail_array: byte length %d is not a multiple of %d (%s)' % (len(data), dt.itemsize, dt))
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
        if o.shape != a.shape:
            raise ValueError('ail_array: shapes differ: %s and %s' % (a.shape, o.shape))
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
    return Array._of(dt, out, a._sh)


def _binary(a, o, sym, reflected, into=None):
    dt = a._dt
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
        return Array._of(a._dt, [_round(a._dt, fn(x)) for x in xs], a._sh)
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
    return Array._of(a._dt, out, a._sh)


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
    if a._dt.is_float:
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
        return Array._of(a._dt, [fix(a._dt, op(x, y)) for x, y in zip(xs, ys)], a._sh)
    run.__name__ = name
    return run


wrapping_add = _intfn('wrapping_add', lambda x, y: x + y, _wrap)
wrapping_sub = _intfn('wrapping_sub', lambda x, y: x - y, _wrap)
wrapping_mul = _intfn('wrapping_mul', lambda x, y: x * y, _wrap)
saturating_add = _intfn('saturating_add', lambda x, y: x + y, _sat)
saturating_sub = _intfn('saturating_sub', lambda x, y: x - y, _sat)


# ---- casts --------------------------------------------------------------------------------------------------------
def _astype(a, dt, rounding, overflow):
    if rounding not in ('trunc', 'nearest'):
        raise ValueError("ail_array: rounding must be 'trunc' or 'nearest', not %r" % (rounding,))
    if overflow not in ('raise', 'saturate', 'wrap'):
        raise ValueError("ail_array: overflow must be 'raise', 'saturate' or 'wrap', not %r" % (overflow,))
    src = a._dt
    xs = a._values()
    if dt.is_float:
        return Array._of(dt, [_round(dt, float(x)) for x in xs], a._sh)
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
            v = x
        if v < dt.lo or v > dt.hi:
            if overflow == 'saturate':
                v = _sat(dt, v)
            elif overflow == 'wrap':
                v = _wrap(dt, v)
            else:
                raise OverflowError('%s cast overflow at index %d' % (dt.name, k))
        out.append(v)
    return Array._of(dt, out, a._sh)


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


def _one_d(a, name):
    if a._sh is not None:
        raise ValueError('ail_array.%s(): 2-D arrays are not built here; reduce one row: ta.%s(M[i])' % (name, name))


def sum(a, acc=None, order=None):
    """The module's sum: exact Python int for int arrays; the fixed blocked order for floats (a Python float)."""
    if not isinstance(a, Array):
        raise TypeError('ail_array.sum() needs an ail_array.Array, not %s' % _type_name(a))
    _one_d(a, 'sum')
    A = _acc(a, acc, 'sum')
    _order(order, 'sum')
    xs = a._values()
    if not a._dt.is_float:
        total = 0
        for x in xs:
            total += x
        return total
    return _fixed_sum(A, xs)


def dot(a, b, acc=None, order=None):
    """sum(a * b) bit for bit: products rounded to the accumulator dtype, then the fixed order; ints are exact."""
    if not isinstance(a, Array) or not isinstance(b, Array):
        raise TypeError('ail_array.dot() needs two ail_array.Array values')
    _one_d(a, 'dot')
    ys = _operand(a, b, 'dot')
    A = _acc(a, acc, 'dot')
    _order(order, 'dot')
    xs = a._values()
    if not a._dt.is_float:
        total = 0
        for x, y in zip(xs, ys):
            total += x * y
        return total
    return _fixed_sum(A, [_round(A, x * y) for x, y in zip(xs, ys)])


def matmul(a, b):
    """Matrix product of two 2-D f64 arrays. Output element (i, j) is `dot(a[i], b[:, j])` bit for bit: the products
    r(a[i,k] * b[k,j]) are added in the fixed order of design 3.5 along k (16 lanes, blocks of 1024, tree), so every
    element has one order whatever the loop nest, the SIMD width or the device. K = 0 gives +0.0."""
    if not isinstance(a, Array) or not isinstance(b, Array):
        raise TypeError('ail_array.matmul() needs two ail_array.Array values')
    if a._sh is None or b._sh is None:
        raise ValueError('ail_array.matmul(): needs two 2-D arrays, not shapes %s and %s' % (a.shape, b.shape))
    if a._dt is not b._dt:
        raise TypeError('ail_array: %s matmul %s: dtypes differ; write a.astype(ta.%s) or b.astype(ta.%s)'
                        % (a._dt, b._dt, b._dt, a._dt))
    if a._dt is not f64:
        raise TypeError('ail_array.matmul(): only f64 arrays are built in this version, not %s' % a._dt)
    m, k = a._sh
    k2, n = b._sh
    if k != k2:
        raise ValueError('ail_array: matmul: shapes %s and %s do not match: %d != %d' % (a._sh, b._sh, k, k2))
    xs = a._values()
    ys = b._values()
    out = []
    for i in range(m):
        row = xs[i * k:(i + 1) * k]
        for j in range(n):
            out.append(_fixed_sum(f64, [row[t] * ys[t * n + j] for t in range(k)]))
    return Array._of(f64, out, (m, n))


def _extreme(a, name, smaller):
    if not isinstance(a, Array):
        raise TypeError('ail_array.%s() needs an ail_array.Array, not %s' % (name, _type_name(a)))
    _one_d(a, name)
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
