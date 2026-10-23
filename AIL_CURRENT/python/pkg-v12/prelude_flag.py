# -*- coding: utf-8 -*-
# prelude_flag.py -- the base classes of `enum.Flag` and `enum.IntFlag` as Python source (enumlib.py adds them after
# prelude_enum.py, only to a program that has a Flag class). The operators, `iter`, `in`, and the lookup of each flag
# class are generated per class by enumlib.py (the general path has no `type(self)(...)`), on top of these.
#
# A member is an instance holding `cname`, `name` (None for a composite with no member in it), `value` and `_idx`
# (the value, which is its hash); composites made by `Flag(v)` are cached, so `P(3) is P(3)`.


def _ail_en_tname(x) -> str:
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
    if isinstance(x, list):
        return "list"
    if isinstance(x, tuple):
        return "tuple"
    if isinstance(x, dict):
        return "dict"
    if isinstance(x, set):
        return "set"
    return "object"


def _ail_en_bits(num: int) -> int:
    n = 0
    while num > 0:
        n = n + (num & 1)
        num = num >> 1
    return n


def _ail_en_bin(num: int, max_bits: int) -> str:
    # enum.bin: two's complement with a leading sign digit, padded to max_bits digits (written without 2 ** n, which an
    # int of 63 bits cannot hold)
    bl = num.bit_length()
    if num >= 0:
        sign = "0b0"
        digits = bin(num)[2:] if num > 0 else ""
    else:
        half = 1 << (bl - 1)
        sign = "0b1"
        digits = bin(~num ^ (half - 1 + half))[2:]
        digits = "0" * (bl - len(digits)) + digits
    if len(digits) < max_bits:
        digits = (sign[-1] * max_bits + digits)[-max_bits:]
    return sign + " " + digits


class _AilFlag(_AilEnum):
    def __repr__(self) -> str:
        if self.name is None:
            return "<%s: %s>" % (self.cname, repr(self.value))
        return "<%s.%s: %s>" % (self.cname, self.name, repr(self.value))

    def __str__(self) -> str:
        if self.name is None:
            return "%s(%s)" % (self.cname, repr(self.value))
        return self.cname + "." + self.name

    def __bool__(self) -> bool:
        return self.value != 0

    def __len__(self) -> int:
        return _ail_en_bits(self.value)

    def __format__(self, spec: str) -> str:
        return format(str(self), spec)


class _AilIntFlag(_AilIntEnum):
    def __repr__(self) -> str:
        if self.name is None:
            return "<%s: %s>" % (self.cname, repr(self.value))
        return "<%s.%s: %s>" % (self.cname, self.name, repr(self.value))

    def __len__(self) -> int:
        return _ail_en_bits(self.value)

    def __format__(self, spec: str) -> str:
        return format(self.value, spec)
