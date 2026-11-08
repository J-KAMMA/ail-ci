"""Derived from PyPy lib_pypy/_marshal.py @ ad61ef7d8e42d7bbdec8d41cdd47d908aaa5241e; MIT License, see stdlib/LICENSE-PYPY-MIT.txt.

Internal Python object serialization, as AIL source.

PyPy's `_marshal.py` writes the historical version-0 layout (text floats, no
object references).  CPython 3.12 is the oracle here, so the writer below
produces CPython's version-4 layout instead: binary floats (`g`), the ASCII
string codes (`z`/`Z` short, `a`/`A` long), base-2**15 longs (`l`) and the
`FLAG_REF` bit on exact ints, floats, strings, bytes, tuples and on shared
lists/dicts.  The reader accepts that layout, including `r` references.

The values the lab programs use are covered: None, True/False, ints (the
32-bit `i` form and the `l` long form, including the int64 boundaries),
binary floats, str (ASCII and UTF-8), bytes, tuples, lists and dicts.  Shared
lists and tuples use CPython's `r` reference form.  A set, frozenset or a user
class is refused by name with `ValueError`.  The integer arithmetic is AIL's
int64, so `dumps`/`loads` stop loudly at the int64 boundary; ints beyond it
cannot be literals in the default build in any case.
"""

__all__ = ["dump", "dumps", "load", "loads", "version"]

version = 4

_TYPE_NULL = 48          # '0'
_TYPE_NONE = 78          # 'N'
_TYPE_FALSE = 70         # 'F'
_TYPE_TRUE = 84          # 'T'
_TYPE_INT = 105          # 'i'
_TYPE_INT64 = 73         # 'I'
_TYPE_FLOAT = 102        # 'f'
_TYPE_BINARY_FLOAT = 103 # 'g'
_TYPE_LONG = 108         # 'l'
_TYPE_STRING = 115       # 's'
_TYPE_INTERNED = 116     # 't'
_TYPE_REF = 114          # 'r'
_TYPE_TUPLE = 40         # '('
_TYPE_SMALL_TUPLE = 41   # ')'
_TYPE_LIST = 91          # '['
_TYPE_DICT = 123         # '{'
_TYPE_UNICODE = 117      # 'u'
_TYPE_SET = 60           # '<'
_TYPE_FROZENSET = 62     # '>'
_TYPE_ASCII = 97         # 'a'
_TYPE_ASCII_INTERNED = 65 # 'A'
_TYPE_SHORT_ASCII = 122  # 'z'
_TYPE_SHORT_ASCII_INTERNED = 90 # 'Z'

_FLAG_REF = 128
_TWO15 = 32768
_TWO52 = 4503599627370496.0
_MIN_INT = -9223372036854775807 - 1


class _Null:
    pass


_NULL = _Null()


def _byte(value):
    b = bytearray(1)
    b[0] = value
    return bytes(b)


def _u32(n):
    return n.to_bytes(4, "little", signed=False)


def _i32(n):
    return n.to_bytes(4, "little", signed=True)


def _pow2(k):
    r = 1.0
    if k >= 0:
        for _i in range(k):
            r = r * 2.0
    else:
        for _i in range(-k):
            r = r / 2.0
    return r


def _float_bytes(x):
    neg = False
    text = str(x)
    if len(text) > 0 and text[0] == "-":
        neg = True
        x = -x
    if x != x:
        expf = 2047
        frac = 1 << 51
    elif x == 0.0:
        expf = 0
        frac = 0
    elif x + x == x:
        expf = 2047
        frac = 0
    else:
        k = 0
        m = x
        while m >= 2.0:
            m = m / 2.0
            k = k + 1
        while m < 1.0:
            m = m * 2.0
            k = k - 1
        if k < -1022:
            expf = 0
            frac = int(m * _pow2(k + 1074))
        else:
            expf = k + 1023
            frac = int((m - 1.0) * _TWO52)
    bits = expf * 4503599627370496 + frac
    lo = bits & 4294967295
    hi = (bits >> 32) & 4294967295
    if neg:
        hi = hi | 2147483648
    return lo.to_bytes(4, "little", signed=False) + hi.to_bytes(4, "little", signed=False)


def _float_from_bytes(raw):
    lo = int.from_bytes(raw[0:4], "little", signed=False)
    hi = int.from_bytes(raw[4:8], "little", signed=False)
    neg = (hi >> 31) != 0
    expf = (hi >> 20) & 2047
    frac = ((hi & 1048575) << 32) | lo
    if expf == 2047:
        if frac == 0:
            v = float("inf")
        else:
            v = float("nan")
    elif expf == 0:
        if frac == 0:
            v = 0.0
        else:
            v = float(frac) * 5e-324
    else:
        v = (1.0 + frac / _TWO52) * _pow2(expf - 1023)
    if neg:
        v = -v
    return v


def _is_name_chars(s):
    for c in s:
        o = ord(c)
        if (o >= 65 and o <= 90) or (o >= 97 and o <= 122) or (o >= 48 and o <= 57) or o == 95:
            continue
        return False
    return True


def _is_ascii(s):
    for c in s:
        if ord(c) > 127:
            return False
    return True


class _Writer:
    def __init__(self, top):
        self.top = top
        self.out = []
        self.refs = []
        self.ids = []
        self.counts = []

    def _count(self, x):
        for i in range(len(self.ids)):
            if self.ids[i] is x:
                self.counts[i] = self.counts[i] + 1
                return
        self.ids.append(x)
        self.counts.append(1)
        if isinstance(x, list) or isinstance(x, tuple):
            for item in x:
                self._count(item)
        elif isinstance(x, dict):
            for key in x:
                self._count(key)
                self._count(x[key])

    def _shared(self, x):
        for i in range(len(self.ids)):
            if self.ids[i] is x:
                return self.counts[i] > 1
        return False

    def _find_ref(self, x):
        for i in range(len(self.refs)):
            if self.refs[i] is x:
                return i
        if isinstance(x, int):
            for i in range(len(self.refs)):
                if isinstance(self.refs[i], int) and self.refs[i] == x:
                    return i
        elif isinstance(x, float):
            for i in range(len(self.refs)):
                if isinstance(self.refs[i], float) and self.refs[i] == x:
                    return i
        elif isinstance(x, str):
            for i in range(len(self.refs)):
                if isinstance(self.refs[i], str) and self.refs[i] == x:
                    return i
        elif isinstance(x, bytes):
            for i in range(len(self.refs)):
                if isinstance(self.refs[i], bytes) and self.refs[i] == x:
                    return i
        return -1

    def _start(self, x):
        idx = self._find_ref(x)
        if idx >= 0:
            self.out.append(_byte(_TYPE_REF))
            self.out.append(_i32(idx))
            return -1
        self.refs.append(x)
        return _FLAG_REF

    def _container_flag(self, x):
        if x is self.top:
            return True
        return self._shared(x)

    def write(self, x):
        if x is None:
            self.out.append(_byte(_TYPE_NONE))
            return
        if x is True:
            self.out.append(_byte(_TYPE_TRUE))
            return
        if x is False:
            self.out.append(_byte(_TYPE_FALSE))
            return
        if isinstance(x, int):
            self._write_int(x)
        elif isinstance(x, float):
            self._write_float(x)
        elif isinstance(x, bytes):
            self._write_bytes(x)
        elif isinstance(x, str):
            self._write_str(x)
        elif isinstance(x, tuple):
            self._write_tuple(x)
        elif isinstance(x, list):
            self._write_list(x)
        elif isinstance(x, dict):
            self._write_dict(x)
        else:
            raise ValueError("unmarshallable object of type %s" % type(x).__name__)

    def _write_int(self, x):
        f = self._start(x)
        if f < 0:
            return
        if x >= -2147483648 and x <= 2147483647:
            self.out.append(_byte(_TYPE_INT | f))
            self.out.append(_i32(x))
            return
        self.out.append(_byte(_TYPE_LONG | f))
        neg = x < 0
        carry = False
        if neg:
            if x == _MIN_INT:
                mag = -(x + 1)
                carry = True
            else:
                mag = -x
        else:
            mag = x
        digits = []
        while mag > 0:
            digits.append(mag & 32767)
            mag = mag >> 15
        if carry:
            i = 0
            while True:
                d = digits[i] + 1
                if d <= 32767:
                    digits[i] = d
                    break
                digits[i] = 0
                i = i + 1
                if i >= len(digits):
                    digits.append(1)
                    break
        n = len(digits)
        if neg:
            n = -n
        self.out.append(_i32(n))
        for d in digits:
            self.out.append(d.to_bytes(2, "little", signed=False))

    def _write_float(self, x):
        f = self._start(x)
        if f < 0:
            return
        self.out.append(_byte(_TYPE_BINARY_FLOAT | f))
        self.out.append(_float_bytes(x))

    def _write_bytes(self, x):
        f = self._start(x)
        if f < 0:
            return
        self.out.append(_byte(_TYPE_STRING | f))
        self.out.append(_u32(len(x)))
        self.out.append(bytes(x))

    def _write_str(self, x):
        f = self._start(x)
        if f < 0:
            return
        raw = x.encode("utf-8")
        interned = _is_name_chars(x)
        if _is_ascii(x):
            if len(raw) < 256:
                if interned:
                    self.out.append(_byte(_TYPE_SHORT_ASCII_INTERNED | f))
                else:
                    self.out.append(_byte(_TYPE_SHORT_ASCII | f))
                self.out.append(_byte(len(raw)))
            else:
                if interned:
                    self.out.append(_byte(_TYPE_ASCII_INTERNED | f))
                else:
                    self.out.append(_byte(_TYPE_ASCII | f))
                self.out.append(_u32(len(raw)))
        else:
            if interned:
                self.out.append(_byte(_TYPE_INTERNED | f))
            else:
                self.out.append(_byte(_TYPE_UNICODE | f))
            self.out.append(_u32(len(raw)))
        self.out.append(raw)

    def _write_tuple(self, x):
        f = self._start(x)
        if f < 0:
            return
        if len(x) < 256:
            self.out.append(_byte(_TYPE_SMALL_TUPLE | f))
            self.out.append(_byte(len(x)))
        else:
            self.out.append(_byte(_TYPE_TUPLE | f))
            self.out.append(_u32(len(x)))
        for item in x:
            self.write(item)

    def _write_list(self, x):
        if self._container_flag(x):
            f = self._start(x)
            if f < 0:
                return
        else:
            f = 0
        self.out.append(_byte(_TYPE_LIST | f))
        self.out.append(_u32(len(x)))
        for item in x:
            self.write(item)

    def _write_dict(self, x):
        if self._container_flag(x):
            f = self._start(x)
            if f < 0:
                return
        else:
            f = 0
        self.out.append(_byte(_TYPE_DICT | f))
        for key in x:
            self.write(key)
            self.write(x[key])
        self.out.append(_byte(_TYPE_NULL))


class _Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.refs = []

    def _take(self, n):
        p = self.pos
        q = p + n
        if q > len(self.data):
            raise EOFError("marshal data too short")
        chunk = self.data[p:q]
        self.pos = q
        return chunk

    def _ref(self, value, flag):
        if flag:
            self.refs.append(value)

    def load(self):
        code = self._take(1)[0]
        flag = (code & _FLAG_REF) != 0
        t = code & 127
        if t == _TYPE_NULL:
            return _NULL
        if t == _TYPE_NONE:
            return None
        if t == _TYPE_FALSE:
            return False
        if t == _TYPE_TRUE:
            return True
        if t == _TYPE_INT:
            v = int.from_bytes(self._take(4), "little", signed=True)
            self._ref(v, flag)
            return v
        if t == _TYPE_INT64:
            v = int.from_bytes(self._take(8), "little", signed=True)
            self._ref(v, flag)
            return v
        if t == _TYPE_LONG:
            n = int.from_bytes(self._take(4), "little", signed=True)
            neg = n < 0
            size = n
            if neg:
                size = -n
            digits = []
            for _i in range(size):
                digits.append(int.from_bytes(self._take(2), "little", signed=False))
            acc = 0
            for i in range(size - 1, -1, -1):
                if neg:
                    acc = acc * _TWO15 - digits[i]
                else:
                    acc = acc * _TWO15 + digits[i]
            self._ref(acc, flag)
            return acc
        if t == _TYPE_BINARY_FLOAT:
            v = _float_from_bytes(self._take(8))
            self._ref(v, flag)
            return v
        if t == _TYPE_STRING:
            n = int.from_bytes(self._take(4), "little", signed=False)
            v = self._take(n)
            self._ref(v, flag)
            return v
        if t == _TYPE_SHORT_ASCII or t == _TYPE_SHORT_ASCII_INTERNED:
            n = self._take(1)[0]
            v = self._take(n).decode("ascii")
            self._ref(v, flag)
            return v
        if t == _TYPE_ASCII or t == _TYPE_ASCII_INTERNED:
            n = int.from_bytes(self._take(4), "little", signed=False)
            v = self._take(n).decode("ascii")
            self._ref(v, flag)
            return v
        if t == _TYPE_UNICODE or t == _TYPE_INTERNED:
            n = int.from_bytes(self._take(4), "little", signed=False)
            v = self._take(n).decode("utf-8")
            self._ref(v, flag)
            return v
        if t == _TYPE_LIST:
            n = int.from_bytes(self._take(4), "little", signed=False)
            v = []
            self._ref(v, flag)
            for _i in range(n):
                v.append(self.load())
            return v
        if t == _TYPE_SMALL_TUPLE or t == _TYPE_TUPLE:
            if t == _TYPE_SMALL_TUPLE:
                n = self._take(1)[0]
            else:
                n = int.from_bytes(self._take(4), "little", signed=False)
            idx = -1
            if flag:
                idx = len(self.refs)
                self.refs.append(None)
            items = []
            for _i in range(n):
                items.append(self.load())
            v = ()
            for item in items:
                v = v + (item,)
            if flag:
                self.refs[idx] = v
            return v
        if t == _TYPE_DICT:
            v = {}
            self._ref(v, flag)
            while True:
                key = self.load()
                if key is _NULL:
                    break
                v[key] = self.load()
            return v
        if t == _TYPE_REF:
            idx = int.from_bytes(self._take(4), "little", signed=True)
            return self.refs[idx]
        if t == _TYPE_SET or t == _TYPE_FROZENSET:
            raise ValueError("marshal: set and frozenset are not built")
        raise ValueError("bad marshal code: %d" % code)


def dumps(x, version_arg=None):
    """dumps(value) -> bytes: the value in CPython 3.12's marshal version-4 layout."""
    w = _Writer(x)
    w._count(x)
    w.write(x)
    return b"".join(w.out)


def loads(data):
    """loads(bytes) -> value: read one value written by dumps()/CPython's marshal."""
    return _Reader(bytes(data)).load()


def dump(x, f, version_arg=None):
    """dump(value, file): write the value to a binary file object."""
    f.write(dumps(x))


def load(f):
    """load(file): read one value from a binary file object."""
    return loads(f.read())
