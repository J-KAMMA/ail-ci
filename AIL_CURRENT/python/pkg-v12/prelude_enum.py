# -*- coding: utf-8 -*-
# prelude_enum.py -- the base classes of `enum.Enum`, `IntEnum` and `StrEnum` as Python source (enumlib.py injects
# them, and creates the members of each enum class after its definition).
#
# A member is an instance holding `cname` (the enum's name), `name`, `value` and `_idx` (its position, which is its
# hash). Members compare by identity (Enum) or by value (IntEnum, StrEnum), print as CPython 3.12 prints them.


class _AilEnum:
    def __init__(self, cname: str, name: str, value, idx: int):
        self.cname = cname
        self.name = name
        self.value = value
        self._idx = idx

    def __repr__(self) -> str:
        return "<%s.%s: %s>" % (self.cname, self.name, repr(self.value))

    def __str__(self) -> str:
        return self.cname + "." + self.name

    def __hash__(self):
        return self._idx

    def __eq__(self, other):
        return self is other


class _AilIntEnum(_AilEnum):
    def __str__(self) -> str:
        return str(self.value)

    def __hash__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, _AilEnum):
            return self.value == other.value
        return self.value == other

    def __lt__(self, other):
        if isinstance(other, _AilEnum):
            return self.value < other.value
        return self.value < other

    def __gt__(self, other):
        if isinstance(other, _AilEnum):
            return self.value > other.value
        return self.value > other

    def __le__(self, other):
        if isinstance(other, _AilEnum):
            return self.value <= other.value
        return self.value <= other

    def __ge__(self, other):
        if isinstance(other, _AilEnum):
            return self.value >= other.value
        return self.value >= other

    def __bool__(self) -> bool:
        return self.value != 0

    def __int__(self) -> int:
        return self.value

    def __index__(self) -> int:
        return self.value

    def __float__(self) -> float:
        return float(self.value)

    def __neg__(self):
        return -self.value

    def __abs__(self):
        return abs(self.value)

    def __add__(self, other):
        if isinstance(other, _AilEnum):
            return self.value + other.value
        return self.value + other

    def __radd__(self, other):
        return other + self.value

    def __sub__(self, other):
        if isinstance(other, _AilEnum):
            return self.value - other.value
        return self.value - other

    def __rsub__(self, other):
        return other - self.value

    def __mul__(self, other):
        if isinstance(other, _AilEnum):
            return self.value * other.value
        return self.value * other

    def __rmul__(self, other):
        return other * self.value

    def __truediv__(self, other):
        if isinstance(other, _AilEnum):
            return self.value / other.value
        return self.value / other

    def __rtruediv__(self, other):
        return other / self.value

    def __floordiv__(self, other):
        if isinstance(other, _AilEnum):
            return self.value // other.value
        return self.value // other

    def __rfloordiv__(self, other):
        return other // self.value

    def __mod__(self, other):
        if isinstance(other, _AilEnum):
            return self.value % other.value
        return self.value % other

    def __rmod__(self, other):
        return other % self.value


class _AilStrEnum(_AilEnum):
    def __str__(self) -> str:
        return self.value

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if isinstance(other, _AilEnum):
            return self.value == other.value
        return self.value == other

    def __lt__(self, other):
        if isinstance(other, _AilEnum):
            return self.value < other.value
        return self.value < other

    def __gt__(self, other):
        if isinstance(other, _AilEnum):
            return self.value > other.value
        return self.value > other

    def __add__(self, other):
        return self.value + other

    def __radd__(self, other):
        return other + self.value

    def __len__(self) -> int:
        return len(self.value)
