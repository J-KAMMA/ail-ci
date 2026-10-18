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
    if tc == "f":
        raise RuntimeError("array typecode 'f' (single precision) is not built; use 'd'")
    raise ValueError("bad typecode (must be b, B, u, w, h, H, i, I, l, L, q, Q, f or d)")


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
    if x is None:
        return "NoneType"
    return "object"


class _AilArray:
    def __init__(self, typecode: str, initializer=None):
        self.typecode = typecode
        self.itemsize = _ail_arr_size(typecode)
        self.data = []
        if initializer is not None:
            for x in initializer:
                self.data.append(_ail_arr_check(typecode, x))

    def append(self, x):
        self.data.append(_ail_arr_check(self.typecode, x))

    def extend(self, it):
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
        self.data.remove(x)

    def index(self, x) -> int:
        return self.data.index(x)

    def count(self, x) -> int:
        return self.data.count(x)

    def reverse(self):
        self.data.reverse()

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

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, i):
        return self.data[i]

    def __setitem__(self, i, x):
        self.data[i] = _ail_arr_check(self.typecode, x)

    def __delitem__(self, i):
        del self.data[i]

    def __iter__(self):
        return list(self.data)

    def __contains__(self, x) -> bool:
        return x in self.data

    def __eq__(self, other):
        if isinstance(other, _AilArray):
            return self.data == other.data
        return False

    def __add__(self, other):
        if other.typecode != self.typecode:
            raise TypeError("bad argument type for built-in operation")
        out = _AilArray(self.typecode)
        out.data = self.data + other.data
        return out

    def __mul__(self, n: int):
        out = _AilArray(self.typecode)
        out.data = self.data * n
        return out

    def __repr__(self) -> str:
        if len(self.data) == 0:
            return "array('" + self.typecode + "')"
        return "array('" + self.typecode + "', " + repr(self.data) + ")"
