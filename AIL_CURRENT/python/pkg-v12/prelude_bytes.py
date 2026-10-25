# prelude_bytes.py -- `bytes` and `bytearray` on the general path, as Python source (branch safetynet).
# safetyrt.py adds it to a program the general path builds when the program uses bytes; the primitives it
# calls (`_ail_b_*`) are C in safetyrt.BYTES. A bytes value holds a str `_s` whose units are its bytes
# (0..255); a bytearray holds a list of int `_a`. The read-only methods of both are written once, on the
# str (the `_ail_bm_*` functions), and the classes wrap the results.
class UnicodeError(ValueError):
    pass


class UnicodeDecodeError(UnicodeError):
    pass


class UnicodeEncodeError(UnicodeError):
    pass


class LookupError(Exception):
    pass


def _ail_b_raise():
    k = _ail_b_errkind()
    m = _ail_b_lasterr()
    if k == 1:
        raise UnicodeEncodeError(m)
    if k == 2:
        raise UnicodeDecodeError(m)
    raise ValueError(m)


def _ail_b_codec_name(encoding):
    parts = []
    punct = False
    for c in encoding:
        o = ord(c)
        if (o >= 48 and o <= 57) or (o >= 65 and o <= 90) or (o >= 97 and o <= 122) or o == 46:
            if punct and parts:
                parts.append("_")
            if o >= 65 and o <= 90:
                c = chr(o + 32)
            parts.append(c)
            punct = False
        else:
            punct = True
    return "".join(parts)


def _ail_b_codec(encoding):
    if not isinstance(encoding, str):
        raise TypeError("encode() argument 'encoding' must be str, not " + type(encoding).__name__)
    e = _ail_b_codec_name(encoding)
    if (e == "utf_8" or e == "utf8" or e == "u8" or e == "utf" or e == "cp65001" or e == "utf8_ucs2"
            or e == "utf8_ucs4"):
        return 0
    if (e == "ascii" or e == "us_ascii" or e == "646" or e == "us" or e == "ansi_x3.4_1968"
            or e == "ansi_x3.4_1986" or e == "ansi_x3_4_1968" or e == "cp367" or e == "csascii" or e == "ibm367"
            or e == "iso646_us" or e == "iso_646.irv_1991" or e == "iso_ir_6"):
        return 1
    if (e == "latin_1" or e == "latin1" or e == "iso_8859_1" or e == "iso8859_1" or e == "8859" or e == "cp819"
            or e == "l1" or e == "latin" or e == "iso_ir_100" or e == "csisolatin1" or e == "ibm819"
            or e == "iso8859" or e == "iso_8859_1_1987"):
        return 2
    raise LookupError("unknown encoding: " + encoding)


def _ail_b_handler(errors):
    if errors == "strict":
        return 0
    if errors == "ignore":
        return 1
    if errors == "replace":
        return 2
    raise LookupError("unknown error handler name '" + str(errors) + "'")


def _ail_b_enc(s, encoding, errors):
    r = _ail_b_encode(s, _ail_b_codec(encoding), _ail_b_handler(errors))
    if r is None:
        _ail_b_raise()
    return r


def _ail_b_dec(s, encoding, errors):
    r = _ail_b_decode(s, _ail_b_codec(encoding), _ail_b_handler(errors))
    if r is None:
        _ail_b_raise()
    return r


def _ail_mkb(s):
    b = bytes()
    b._s = s
    return b


def _ail_mkba(s):
    b = bytearray()
    b._a = _ail_b_ints(s)
    return b


def _ail_bs(x):
    if isinstance(x, bytes):
        return x._s
    if isinstance(x, bytearray):
        return _ail_b_from_ints(x._a)
    raise TypeError("a bytes-like object is required, not '" + type(x).__name__ + "'")


def _ail_bsub(x):
    if isinstance(x, int):
        if x < 0 or x > 255:
            raise ValueError("byte must be in range(0, 256)")
        return chr(x)
    if isinstance(x, bytes):
        return x._s
    if isinstance(x, bytearray):
        return _ail_b_from_ints(x._a)
    raise TypeError("argument should be integer or bytes-like object, not '" + type(x).__name__ + "'")


def _ail_bcontains(x):
    if isinstance(x, int):
        if x < 0 or x > 255:
            raise ValueError("byte must be in range(0, 256)")
        return chr(x)
    if isinstance(x, bytes):
        return x._s
    if isinstance(x, bytearray):
        return _ail_b_from_ints(x._a)
    raise TypeError("a bytes-like object is required, not '" + type(x).__name__ + "'")


def _ail_b_source(source, encoding, errors):
    if source is None:
        if encoding is not None or errors is not None:
            raise TypeError("encoding or errors without sequence argument")
        return ""
    if isinstance(source, str):
        if encoding is None:
            raise TypeError("string argument without an encoding")
        return _ail_b_enc(source, encoding, "strict" if errors is None else errors)
    if encoding is not None or errors is not None:
        raise TypeError("encoding or errors without a string argument")
    if isinstance(source, int):
        if source < 0:
            raise ValueError("negative count")
        return "\x00" * source
    if isinstance(source, bytes):
        return source._s
    if isinstance(source, bytearray):
        return _ail_b_from_ints(source._a)
    return _ail_b_from_ints(source)


def _ail_b_bound(x):
    if x is None:
        return None
    return _ail_b_index(x)


def _ail_b_rng(n, start, end):
    st = 0
    en = n
    if start is not None:
        st = _ail_b_bound(start)
    if end is not None:
        en = _ail_b_bound(end)
    if start is not None:
        if st < 0:
            if st < -n:
                st = 0
            else:
                st = st + n
    if end is not None:
        if en > n:
            en = n
        elif en < 0:
            if en < -n:
                en = 0
            else:
                en = en + n
    return (st, en)


def _ail_bm_split(s, sep, maxsplit):
    if sep is None:
        return _ail_b_split_ws(s, maxsplit, False)
    p = _ail_bs(sep)
    if len(p) == 0:
        raise ValueError("empty separator")
    if maxsplit < 0:
        return s.split(p)
    return s.split(p, maxsplit)


def _ail_bm_rsplit(s, sep, maxsplit):
    if sep is None:
        return _ail_b_split_ws(s, maxsplit, True)
    p = _ail_bs(sep)
    if len(p) == 0:
        raise ValueError("empty separator")
    if maxsplit < 0:
        return s.rsplit(p)
    return s.rsplit(p, maxsplit)


def _ail_bm_strip(s, chars):
    if chars is None:
        return _ail_b_strip_ws(s, 0)
    return s.strip(_ail_bs(chars))


def _ail_bm_lstrip(s, chars):
    if chars is None:
        return _ail_b_strip_ws(s, 1)
    return s.lstrip(_ail_bs(chars))


def _ail_bm_rstrip(s, chars):
    if chars is None:
        return _ail_b_strip_ws(s, 2)
    return s.rstrip(_ail_bs(chars))


def _ail_b_tail(s, p, st, en, right):
    if st > len(s):
        return False
    if en - st < len(p):
        return False
    if right:
        return s[en - len(p):en] == p
    return s[st:st + len(p)] == p


def _ail_b_affix(s, x, start, end, right, name):
    st, en = _ail_b_rng(len(s), start, end)
    if isinstance(x, tuple):
        for item in x:
            if not (isinstance(item, bytes) or isinstance(item, bytearray)):
                raise TypeError("a bytes-like object is required, not '" + type(item).__name__ + "'")
            if _ail_b_tail(s, _ail_bs(item), st, en, right):
                return True
        return False
    if not (isinstance(x, bytes) or isinstance(x, bytearray)):
        raise TypeError(name + " first arg must be bytes or a tuple of bytes, not " + type(x).__name__)
    return _ail_b_tail(s, _ail_bs(x), st, en, right)


def _ail_bm_startswith(s, prefix, start, end):
    return _ail_b_affix(s, prefix, start, end, False, "startswith")


def _ail_bm_endswith(s, suffix, start, end):
    return _ail_b_affix(s, suffix, start, end, True, "endswith")


def _ail_bm_find(s, sub, start, end):
    p = _ail_bsub(sub)
    st, en = _ail_b_rng(len(s), start, end)
    if en - st < len(p):
        return -1
    r = s[st:en].find(p)
    if r < 0:
        return -1
    return r + st


def _ail_bm_rfind(s, sub, start, end):
    p = _ail_bsub(sub)
    st, en = _ail_b_rng(len(s), start, end)
    if en - st < len(p):
        return -1
    r = s[st:en].rfind(p)
    if r < 0:
        return -1
    return r + st


def _ail_bm_index(s, sub, start, end):
    r = _ail_bm_find(s, sub, start, end)
    if r < 0:
        raise ValueError("subsection not found")
    return r


def _ail_bm_rindex(s, sub, start, end):
    r = _ail_bm_rfind(s, sub, start, end)
    if r < 0:
        raise ValueError("subsection not found")
    return r


def _ail_bm_count(s, sub, start, end):
    p = _ail_bsub(sub)
    st, en = _ail_b_rng(len(s), start, end)
    if en - st < len(p):
        return 0
    if len(p) == 0:
        return en - st + 1
    return s[st:en].count(p)


def _ail_bm_replace(s, old, new, count):
    o = _ail_bs(old)
    n = _ail_bs(new)
    if count < 0:
        return s.replace(o, n)
    return s.replace(o, n, count)


def _ail_bm_join(s, iterable):
    parts = []
    i = 0
    for x in iterable:
        if isinstance(x, bytes):
            parts.append(x._s)
        elif isinstance(x, bytearray):
            parts.append(_ail_b_from_ints(x._a))
        else:
            raise TypeError("sequence item " + str(i) + ": expected a bytes-like object, " + type(x).__name__ + " found")
        i += 1
    return s.join(parts)


def _ail_bm_partition(s, sep):
    p = _ail_bs(sep)
    if len(p) == 0:
        raise ValueError("empty separator")
    return s.partition(p)


def _ail_bm_rpartition(s, sep):
    p = _ail_bs(sep)
    if len(p) == 0:
        raise ValueError("empty separator")
    return s.rpartition(p)


def _ail_bm_removeprefix(s, prefix):
    p = _ail_bs(prefix)
    if s.startswith(p):
        return s[len(p):]
    return s


def _ail_bm_removesuffix(s, suffix):
    p = _ail_bs(suffix)
    if len(p) > 0 and s.endswith(p):
        return s[:len(s) - len(p)]
    return s


_AIL_B_DEFAULT_FILL = []


def _ail_b_fill(fillchar, name):
    if fillchar is _AIL_B_DEFAULT_FILL:
        return " "
    if fillchar is None:
        raise TypeError(name + "() argument 2 must be a byte string of length 1, not None")
    if not (isinstance(fillchar, bytes) or isinstance(fillchar, bytearray)):
        raise TypeError(name + "() argument 2 must be a byte string of length 1, not " + type(fillchar).__name__)
    f = _ail_bs(fillchar)
    if len(f) != 1:
        raise TypeError(name + "() argument 2 must be a byte string of length 1, not " + type(fillchar).__name__)
    return f


def _ail_bm_center(s, width, fillchar):
    return s.center(width, _ail_b_fill(fillchar, "center"))


def _ail_bm_ljust(s, width, fillchar):
    return s.ljust(width, _ail_b_fill(fillchar, "ljust"))


def _ail_bm_rjust(s, width, fillchar):
    return s.rjust(width, _ail_b_fill(fillchar, "rjust"))


def _ail_bm_translate(s, table, delete):
    t = None
    if table is not None:
        t = _ail_bs(table)
    d = None
    if delete is not None:
        d = _ail_bs(delete)
    return _ail_b_translate(s, t, d)


def _ail_bm_decode(s, encoding, errors):
    return _ail_b_dec(s, encoding, errors)


def _ail_b_maketrans(frm, to):
    a = _ail_bs(frm)
    b = _ail_bs(to)
    if len(a) != len(b):
        raise ValueError("maketrans arguments must have same length")
    table = list(range(256))
    for i in range(len(a)):
        table[ord(a[i])] = ord(b[i])
    return _ail_b_from_ints(table)


def _ail_bm_hex(s, args):
    """bytes.hex([sep[, bytes_per_sep]]): hex() digits grouped by bytes_per_sep, as CPython 3.12 does.
    A positive group counts from the left (the first group is the remainder), a negative one from
    the right (the last group is the remainder); 0 is one group, so no separator at all."""
    text = _ail_b_hex(s)
    if len(args) == 0:
        return text
    if len(args) > 2:
        raise TypeError("hex() takes at most 2 arguments (" + str(len(args)) + " given)")
    group = 1
    if len(args) == 2:
        # CPython parses bytes_per_sep as a C int before the method body looks at sep, so the
        # conversion error comes first and the range is that of a 32-bit int, not of an int64.
        group = args[1]
        if not isinstance(group, int):
            raise TypeError("'" + type(group).__name__ + "' object cannot be interpreted as an integer")
        if group < -2147483648 or group > 2147483647:
            raise OverflowError("Python int too large to convert to C int")
    sep = args[0]
    n = len(sep)            # a sep with no len() is CPython's own TypeError from this length test
    if not isinstance(sep, (str, bytes)):
        raise TypeError("sep must be str or bytes.")
    if n != 1:
        raise ValueError("sep must be length 1.")
    if isinstance(sep, bytes):
        sep = _ail_bs(sep)
    if ord(sep) > 127:
        raise ValueError("sep must be ASCII.")
    count = len(text) // 2
    if group == 0 or group >= count or group <= -count:
        return text
    pieces = []
    if group > 0:
        i = 0
        while i < count:
            step = group
            if i == 0 and count % group != 0:
                step = count % group
            pieces.append(text[2 * i:2 * (i + step)])
            i = i + step
    else:
        g = -group
        i = count
        while i > 0:
            step = g
            if i == count and count % g != 0:
                step = count % g
            pieces.append(text[2 * (i - step):2 * i])
            i = i - step
        pieces.reverse()
    return sep.join(pieces)


def _ail_b_fromhex_s(text):
    r = _ail_b_fromhex(text)
    if r is None:
        _ail_b_raise()
    return r


def _ail_b_cmp_other(other, op, me):
    if isinstance(other, bytes):
        return other._s
    if isinstance(other, bytearray):
        return _ail_b_from_ints(other._a)
    raise TypeError("'" + op + "' not supported between instances of '" + me + "' and '" + type(other).__name__ + "'")


def _ail_b_int(s, text):
    text = text[:200]
    if not _ail_b_numsafe(s):
        raise ValueError("invalid literal for int() with base 10: " + text)
    try:
        return int(s)
    except ValueError:
        raise ValueError("invalid literal for int() with base 10: " + text)


def _ail_b_float(s, text):
    if not _ail_b_numsafe(s):
        raise ValueError("could not convert string to float: " + text)
    try:
        return float(s)
    except ValueError:
        raise ValueError("could not convert string to float: " + text)


def _ail_b_idx(n, i, what):
    if not isinstance(i, int):
        raise TypeError(what + " indices must be integers or slices, not " + type(i).__name__)
    if i < 0:
        i = i + n
    if i < 0 or i >= n:
        if what == "byte":
            raise IndexError("index out of range")
        raise IndexError("bytearray index out of range")
    return i


class bytes:
    def __init__(self, source=None, encoding=None, errors=None):
        self._s = _ail_b_source(source, encoding, errors)

    def __len__(self):
        return len(self._s)

    def __getitem__(self, i):
        if isinstance(i, slice):
            return _ail_mkb(_ail_slice_get(self._s, i.start, i.stop, i.step))
        return ord(self._s[_ail_b_idx(len(self._s), i, "byte")])

    def __iter__(self):
        return iter(_ail_b_ints(self._s))

    def __contains__(self, x):
        return _ail_bcontains(x) in self._s

    def __eq__(self, other):
        if isinstance(other, bytes):
            return self._s == other._s
        if isinstance(other, bytearray):
            return self._s == _ail_b_from_ints(other._a)
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self._s < _ail_b_cmp_other(other, "<", "bytes")

    def __le__(self, other):
        return self._s <= _ail_b_cmp_other(other, "<=", "bytes")

    def __gt__(self, other):
        return self._s > _ail_b_cmp_other(other, ">", "bytes")

    def __ge__(self, other):
        return self._s >= _ail_b_cmp_other(other, ">=", "bytes")

    def __hash__(self):
        return hash(self._s)

    def __add__(self, other):
        if isinstance(other, bytes):
            return _ail_mkb(self._s + other._s)
        if isinstance(other, bytearray):
            return _ail_mkb(self._s + _ail_b_from_ints(other._a))
        tn = type(other).__name__
        if tn == 'deque' or tn.startswith('_AilDeque'):
            tn = 'collections.deque'
        elif tn == 'defaultdict':
            tn = 'collections.defaultdict'
        raise TypeError("can't concat " + tn + " to bytes")

    def __mul__(self, n):
        if not isinstance(n, int):
            tn = type(n).__name__
            if tn == 'deque':
                tn = 'collections.deque'
            raise TypeError("can't multiply sequence by non-int of type '" + tn + "'")
        return _ail_mkb(self._s * n)

    def __rmul__(self, n):
        if not isinstance(n, int):
            tn = type(n).__name__
            raise TypeError("can't multiply sequence by non-int of type '"
                            + (type(self).__name__ if tn in ('list', 'tuple', 'str', 'bytes', 'bytearray', 'deque') else tn) + "'")
        return self.__mul__(n)

    def __mod__(self, args):
        return _ail_mkb(_ail_b_percent(self._s, args))

    def __bool__(self):
        return len(self._s) > 0

    def __repr__(self):
        return "b" + _ail_b_repr(self._s)

    def __str__(self):
        return "b" + _ail_b_repr(self._s)

    def __int__(self):
        return _ail_b_int(self._s, "b" + _ail_b_repr(self._s))

    def __float__(self):
        return _ail_b_float(self._s, "b" + _ail_b_repr(self._s))

    @staticmethod
    def maketrans(frm, to):
        return _ail_mkb(_ail_b_maketrans(frm, to))

    @staticmethod
    def fromhex(text):
        return _ail_mkb(_ail_b_fromhex_s(text))

#@METHODS bytes _ail_mkb self._s


class bytearray:
    def __init__(self, source=None, encoding=None, errors=None):
        if isinstance(source, int) and encoding is None and errors is None:
            if source < 0:
                raise ValueError("negative count")
            self._a = [0] * source
        else:
            self._a = _ail_b_ints(_ail_b_source(source, encoding, errors))

    def __len__(self):
        return len(self._a)

    def __getitem__(self, i):
        a = self._a
        if isinstance(i, int) and 0 <= i < len(a):
            return a[i]
        if isinstance(i, slice):
            r = bytearray()
            r._a = a[i]
            return r
        return a[_ail_b_idx(len(a), i, "bytearray")]

    def __setitem__(self, i, v):
        a = self._a
        if isinstance(i, int) and isinstance(v, int) and 0 <= i < len(a) and 0 <= v < 256:
            a[i] = v
            return
        if isinstance(i, slice):
            if isinstance(v, int):
                raise TypeError("can assign only bytes, buffers, or iterables of ints in range(0, 256)")
            self._a[i] = _ail_b_ints(_ail_b_source(v, None, None))
            return
        if not isinstance(v, int):
            raise TypeError("'" + type(v).__name__ + "' object cannot be interpreted as an integer")
        if v < 0 or v > 255:
            raise ValueError("byte must be in range(0, 256)")
        self._a[_ail_b_idx(len(self._a), i, "bytearray")] = v

    def __delitem__(self, i):
        if isinstance(i, slice):
            del self._a[i]
            return
        del self._a[_ail_b_idx(len(self._a), i, "bytearray")]

    def __iter__(self):
        return iter(self._a)

    def __contains__(self, x):
        return _ail_bcontains(x) in _ail_b_from_ints(self._a)

    def __eq__(self, other):
        if isinstance(other, bytearray):
            return self._a == other._a
        if isinstance(other, bytes):
            return _ail_b_from_ints(self._a) == other._s
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return _ail_b_from_ints(self._a) < _ail_b_cmp_other(other, "<", "bytearray")

    def __le__(self, other):
        return _ail_b_from_ints(self._a) <= _ail_b_cmp_other(other, "<=", "bytearray")

    def __gt__(self, other):
        return _ail_b_from_ints(self._a) > _ail_b_cmp_other(other, ">", "bytearray")

    def __ge__(self, other):
        return _ail_b_from_ints(self._a) >= _ail_b_cmp_other(other, ">=", "bytearray")

    def __hash__(self):
        raise TypeError("unhashable type: 'bytearray'")

    def _ail_concat_name(self, other):
        tn = type(other).__name__
        if tn == 'deque' or tn.startswith('_AilDeque'):
            return 'collections.deque'
        if tn == 'defaultdict':
            return 'collections.defaultdict'
        return tn

    def __add__(self, other):
        if not isinstance(other, (bytes, bytearray)):
            raise TypeError("can't concat " + self._ail_concat_name(other) + " to bytearray")
        r = bytearray()
        r._a = self._a + _ail_b_ints(_ail_bs(other))
        return r

    def __iadd__(self, other):
        if not isinstance(other, (bytes, bytearray)):
            raise TypeError("can't concat " + self._ail_concat_name(other) + " to bytearray")
        self._a.extend(_ail_b_ints(_ail_bs(other)))
        return self

    def __mul__(self, n):
        if not isinstance(n, int):
            tn = type(n).__name__
            if tn == 'deque':
                tn = 'collections.deque'
            raise TypeError("can't multiply sequence by non-int of type '" + tn + "'")
        r = bytearray()
        r._a = self._a * n
        return r

    def __rmul__(self, n):
        if not isinstance(n, int):
            tn = type(n).__name__
            raise TypeError("can't multiply sequence by non-int of type '"
                            + (type(self).__name__ if tn in ('list', 'tuple', 'str', 'bytes', 'bytearray', 'deque') else tn) + "'")
        return self.__mul__(n)

    def __mod__(self, args):
        return _ail_mkba(_ail_b_percent(_ail_b_from_ints(self._a), args))

    def __bool__(self):
        return len(self._a) > 0

    def __repr__(self):
        return "bytearray(b" + _ail_b_repr(_ail_b_from_ints(self._a)) + ")"

    def __str__(self):
        return "bytearray(b" + _ail_b_repr(_ail_b_from_ints(self._a)) + ")"

    def __int__(self):
        s = _ail_b_from_ints(self._a)
        return _ail_b_int(s, "b" + _ail_b_repr(s))

    def __float__(self):
        s = _ail_b_from_ints(self._a)
        return _ail_b_float(s, "bytearray(b" + _ail_b_repr(s) + ")")

    def append(self, x):
        if not isinstance(x, int):
            raise TypeError("'" + type(x).__name__ + "' object cannot be interpreted as an integer")
        if x < 0 or x > 255:
            raise ValueError("byte must be in range(0, 256)")
        self._a.append(x)

    def extend(self, src):
        if isinstance(src, str):
            raise TypeError("expected iterable of integers; got: 'str'")
        self._a.extend(_ail_b_ints(_ail_b_source(src, None, None)))

    def insert(self, i, x):
        if not isinstance(x, int):
            raise TypeError("'" + type(x).__name__ + "' object cannot be interpreted as an integer")
        if x < 0 or x > 255:
            raise ValueError("byte must be in range(0, 256)")
        self._a.insert(i, x)

    def pop(self, i=-1):
        if len(self._a) == 0:
            raise IndexError("pop from empty bytearray")
        return self._a.pop(_ail_b_idx(len(self._a), i, "bytearray"))

    def remove(self, x):
        if not isinstance(x, int):
            raise TypeError("'" + type(x).__name__ + "' object cannot be interpreted as an integer")
        if x in self._a:
            self._a.remove(x)
        else:
            raise ValueError("value not found in bytearray")

    def reverse(self):
        self._a.reverse()

    def clear(self):
        self._a = []

    def copy(self):
        r = bytearray()
        r._a = list(self._a)
        return r

    @staticmethod
    def maketrans(frm, to):
        return _ail_mkb(_ail_b_maketrans(frm, to))

    @staticmethod
    def fromhex(text):
        return _ail_mkba(_ail_b_fromhex_s(text))

#@METHODS bytearray _ail_mkba _ail_b_from_ints(self._a)


def _ail_b_percent(fmt, args):
    vals = []
    if isinstance(args, tuple):
        for a in args:
            vals.append(_ail_b_pval(a))
    else:
        vals.append(_ail_b_pval(args))
    return _ail_pct(fmt, tuple(vals))


def _ail_b_pval(a):
    if isinstance(a, bytes):
        return a._s
    if isinstance(a, bytearray):
        return _ail_b_from_ints(a._a)
    if isinstance(a, str):
        raise TypeError("%b requires a bytes-like object, or an object that implements __bytes__, not 'str'")
    return a


def _ail_str_encode(s, encoding="utf-8", errors="strict"):
    if not isinstance(s, str):
        raise AttributeError("'" + type(s).__name__ + "' object has no attribute 'encode'")
    return _ail_mkb(_ail_b_enc(s, encoding, errors))


def _ail_str_decode(x, encoding="utf-8", errors="strict"):
    return _ail_b_dec(_ail_bs(x), encoding, errors)


def _ail_int2(x, base):
    if isinstance(x, bytes) or isinstance(x, bytearray):
        s = _ail_bs(x)
        text = ("b" + _ail_b_repr(s)) if isinstance(x, bytearray) else repr(x)
        text = text[:200]
        if not _ail_b_numsafe(s):
            raise ValueError("invalid literal for int() with base " + str(base) + ": " + text)
        try:
            return int(s, base)
        except ValueError:
            raise ValueError("invalid literal for int() with base " + str(base) + ": " + text)
    return int(x, base)


def _ail_to_bytes(n, length=1, byteorder="big", signed=False):
    if not isinstance(n, int):
        raise AttributeError("'" + type(n).__name__ + "' object has no attribute 'to_bytes'")
    if byteorder != "big" and byteorder != "little":
        raise ValueError("byteorder must be either 'little' or 'big'")
    if length < 0:
        raise ValueError("length argument must be non-negative")
    if n < 0 and not signed:
        raise OverflowError("can't convert negative int to unsigned")
    v = n
    out = []
    for i in range(length):
        out.append(v & 255)
        v = v >> 8
    if signed:
        if length == 0:
            ok = n == 0 or n == -1
        else:
            top = out[length - 1]
            ok = (v == 0 and top < 128) or (v == -1 and top >= 128)
        if not ok:
            raise OverflowError("int too big to convert")
    elif v != 0:
        raise OverflowError("int too big to convert")
    if byteorder == "big":
        out.reverse()
    return _ail_mkb(_ail_b_from_ints(out))


def _ail_from_bytes(data, byteorder="big", signed=False):
    if byteorder != "big" and byteorder != "little":
        raise ValueError("byteorder must be either 'little' or 'big'")
    if data is None or isinstance(data, int) or isinstance(data, str):
        raise TypeError("cannot convert '" + type(data).__name__ + "' object to bytes")
    s = _ail_b_source(data, None, None)
    vals = _ail_b_ints(s)
    if byteorder == "little":
        vals.reverse()
    v = 0
    i = 0
    n = len(vals)
    while i < n:
        x = vals[i]
        if i == 0 and signed and x >= 128:
            x = x - 256
        v = v * 256 + x
        i += 1
    return v


class _AilStdoutBuffer:
    def write(self, data):
        return _ail_b_write(_ail_bs(data))

    def flush(self):
        return None


class _AilStdinBuffer:
    def read(self, n=-1):
        return _ail_mkb(_ail_b_stdin(n))


def read_stdin_bytes(n):
    return _ail_mkb(_ail_b_stdin(n))


def write_stdout_bytes(data):
    return _ail_b_write(_ail_bs(data))
