# -*- coding: utf-8 -*-
# prelude_array.py -- `array.array` for the integer and double typecodes as Python source (smalllib5.py injects it).
# 'b' 'B' 'h' 'H' 'i' 'I' 'l' 'L' 'q' 'Q' (ints in the C range of the type) and 'd'. The elements are held in a list.


def _ail_arr_size(tc: str) -> int:
    if tc == "b" or tc == "B":
        return 1
    if tc == "h" or tc == "H":
        return 2
    if tc == "i" or tc == "I":
        return 4
    if tc == "l" or tc == "L" or tc == "q" or tc == "Q" or tc == "d":
        return 8
    return 0


def _ail_arr_check(tc: str, x):
    if tc == "d":
        if isinstance(x, float):
            return x
        if isinstance(x, int):
            return float(x)
        raise TypeError("must be real number, not " + _ail_arr_tname(x))
    if isinstance(x, float) or isinstance(x, str) or x is None:
        raise TypeError("'" + _ail_arr_tname(x) + "' object cannot be interpreted as an integer")
    v = int(x)
    if tc == "b" or tc == "B" or tc == "h":
        if v < -32768:
            raise OverflowError("signed short integer is less than minimum")
        if v > 32767:
            raise OverflowError("signed short integer is greater than maximum")
        if tc == "b":
            if v < -128:
                raise OverflowError("signed char is less than minimum")
            if v > 127:
                raise OverflowError("signed char is greater than maximum")
        if tc == "B":
            if v < 0:
                raise OverflowError("unsigned byte integer is less than minimum")
            if v > 255:
                raise OverflowError("unsigned byte integer is greater than maximum")
        return v
    if tc == "H" or tc == "i":
        if v < -2147483648:
            raise OverflowError("signed integer is less than minimum")
        if v > 2147483647:
            raise OverflowError("signed integer is greater than maximum")
        if tc == "H":
            if v < 0:
                raise OverflowError("unsigned short is less than minimum")
            if v > 65535:
                raise OverflowError("unsigned short is greater than maximum")
        return v
    if tc == "I":
        if v < 0:
            raise OverflowError("can't convert negative value to unsigned int")
        if v > 4294967295:
            raise OverflowError("unsigned int is greater than maximum")
        return v
    if tc == "L":
        if v < 0:
            raise OverflowError("can't convert negative value to unsigned int")
        return v
    if tc == "Q":
        if v < 0:
            raise OverflowError("can't convert negative int to unsigned")
        return v
    return v


def _ail_arr_tname(x) -> str:
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "str"
    if isinstance(x, list):
        return "list"
    if isinstance(x, tuple):
        return "tuple"
    if isinstance(x, dict):
        return "dict"
    if x is None:
        return "NoneType"
    return "object"


def _ail_arr_bad_kw():
    raise TypeError("array.array() takes no keyword arguments")


class _AilArrayMissing:
    pass


_AIL_ARR_MISSING = _AilArrayMissing()


class _AilArray:
    def __init__(self, typecode: str, initializer=None):
        self.typecode = typecode
        size = _ail_arr_size(typecode)
        if size == 0:
            if typecode == "f":
                raise RuntimeError("array typecode 'f' (single precision) is not built; use 'd'")
            raise ValueError("bad typecode (must be b, B, u, h, H, i, I, l, L, q, Q, f or d)")
        self.itemsize = size
        self.data = []
        if initializer is not None:
            for x in initializer:
                self.data.append(_ail_arr_check(typecode, x))

    def append(self, x):
        self.data.append(_ail_arr_check(self.typecode, x))

    def extend(self, it):
        if isinstance(it, _AilArray) and it.typecode != self.typecode:
            raise TypeError("can only extend with array of same kind")
        for x in it:
            self.data.append(_ail_arr_check(self.typecode, x))

    def insert(self, i: int, x):
        self.data.insert(i, _ail_arr_check(self.typecode, x))

    def pop(self, i: int = -1):
        if len(self.data) == 0:
            raise IndexError("pop from empty array")
        if i < -len(self.data) or i >= len(self.data):
            raise IndexError("pop index out of range")
        return self.data.pop(i)

    def remove(self, x):
        try:
            self.data.remove(x)
        except ValueError:
            raise ValueError("array.remove(x): x not in array")

    def index(self, x, start=_AIL_ARR_MISSING, stop=_AIL_ARR_MISSING) -> int:
        if start is not _AIL_ARR_MISSING and not isinstance(start, int):
            raise TypeError("slice indices must be integers or have an __index__ method")
        if stop is not _AIL_ARR_MISSING and not isinstance(stop, int):
            raise TypeError("slice indices must be integers or have an __index__ method")
        try:
            if start is _AIL_ARR_MISSING:
                return self.data.index(x)
            if stop is _AIL_ARR_MISSING:
                return self.data.index(x, start)
            return self.data.index(x, start, stop)
        except ValueError:
            raise ValueError("array.index(x): x not in array")

    def count(self, x) -> int:
        return self.data.count(x)

    def reverse(self):
        self.data.reverse()

    def fromlist(self, values):
        if not isinstance(values, list):
            raise TypeError("arg must be list")
        try:
            reversed(values)
        except TypeError:
            raise TypeError("arg must be list")
        for x in values:
            self.data.append(_ail_arr_check(self.typecode, x))

    def tolist(self) -> list:
        return list(self.data)

    def byteswap(self):
        size = self.itemsize
        if self.typecode == "d":
            raise RuntimeError("array.byteswap() of doubles is not built")
        signed = self.typecode == "b" or self.typecode == "h" or self.typecode == "i" or self.typecode == "l" or self.typecode == "q"
        mod = 1
        k = 0
        while k < size:
            mod = mod * 256
            k = k + 1
        out = []
        for v in self.data:
            u = v
            if u < 0:
                u = u + mod
            r = 0
            k = 0
            while k < size:
                r = r * 256 + u % 256
                u = u // 256
                k = k + 1
            if signed and r >= mod // 2:
                r = r - mod
            out.append(r)
        self.data = out

    def _position(self, i, assignment):
        if not isinstance(i, int):
            raise TypeError("array indices must be integers")
        n = len(self.data)
        if i < 0:
            i = i + n
        if i < 0 or i >= n:
            if assignment:
                raise IndexError("array assignment index out of range")
            raise IndexError("array index out of range")
        return i

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, i):
        if type(i).__name__ == 'slice':
            out = _AilArray(self.typecode)
            out.data = self.data[i]
            return out
        return self.data[self._position(i, False)]

    def __setitem__(self, i, x):
        if type(i).__name__ == 'slice':
            if not isinstance(x, _AilArray):
                raise TypeError('can only assign array (not "%s") to array slice' % _ail_arr_tname(x))
            if x.typecode != self.typecode:
                raise TypeError("bad argument type for built-in operation")
            try:
                self.data[i] = x.data
            except ValueError as e:
                raise ValueError(str(e).replace("sequence", "array", 1))
            return
        self.data[self._position(i, True)] = _ail_arr_check(self.typecode, x)

    def __delitem__(self, i):
        if type(i).__name__ == 'slice':
            del self.data[i]
            return
        del self.data[self._position(i, True)]

    def __iter__(self):
        return list(self.data)

    def __contains__(self, x) -> bool:
        return x in self.data

    def __eq__(self, other):
        if isinstance(other, _AilArray):
            return self.data == other.data
        return False

    def __ne__(self, other):
        if isinstance(other, _AilArray):
            return self.data != other.data
        return True

    def __lt__(self, other):
        if not isinstance(other, _AilArray):
            raise TypeError("'<' not supported between instances of 'array.array' and '%s'" % _ail_arr_tname(other))
        return self.data < other.data

    def __le__(self, other):
        if not isinstance(other, _AilArray):
            raise TypeError("'<=' not supported between instances of 'array.array' and '%s'" % _ail_arr_tname(other))
        return self.data <= other.data

    def __gt__(self, other):
        if not isinstance(other, _AilArray):
            raise TypeError("'>' not supported between instances of 'array.array' and '%s'" % _ail_arr_tname(other))
        return self.data > other.data

    def __ge__(self, other):
        if not isinstance(other, _AilArray):
            raise TypeError("'>=' not supported between instances of 'array.array' and '%s'" % _ail_arr_tname(other))
        return self.data >= other.data

    def _check_add(self, other, verb):
        if not isinstance(other, _AilArray):
            if verb == "extend":
                raise TypeError('can only extend array with array (not "%s")' % _ail_arr_tname(other))
            raise TypeError('can only append array (not "%s") to array' % _ail_arr_tname(other))
        if other.typecode != self.typecode:
            if verb == "extend":
                raise TypeError("can only extend with array of same kind")
            raise TypeError("bad argument type for built-in operation")

    def __add__(self, other):
        self._check_add(other, "append")
        out = _AilArray(self.typecode)
        out.data = self.data + other.data
        return out

    def __iadd__(self, other):
        self._check_add(other, "extend")
        self.data.extend(other.data)
        return self

    def __mul__(self, n):
        if not isinstance(n, int):
            raise TypeError("can't multiply sequence by non-int of type '%s'" % _ail_arr_tname(n))
        out = _AilArray(self.typecode)
        out.data = self.data * n
        return out

    def __rmul__(self, n):
        if not isinstance(n, int):
            raise TypeError("can't multiply sequence by non-int of type '%s'" % _ail_arr_tname(n))
        out = _AilArray(self.typecode)
        out.data = self.data * n
        return out

    def __imul__(self, n):
        if not isinstance(n, int):
            raise TypeError("can't multiply sequence by non-int of type '%s'" % _ail_arr_tname(n))
        self.data = self.data * n
        return self

    def __repr__(self) -> str:
        if len(self.data) == 0:
            return "array('" + self.typecode + "')"
        return "array('" + self.typecode + "', " + repr(self.data) + ")"
