# -*- coding: utf-8 -*-
# prelude_enum.py -- the base classes of `enum.Enum`, `IntEnum` and `StrEnum` as Python source (enumlib.py injects
# them, and creates the members of each enum class after its definition).
#
# A member is an instance holding `cname` (the enum's name), `name`, `value` and `_idx` (its position, which is its
# hash). Members compare by identity (Enum) or by value (IntEnum, StrEnum), print as CPython 3.12 prints them.


def _ail_en_noattr(cname: str, attr: str):
    raise AttributeError("type object '" + cname + "' has no attribute '" + attr + "'")


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

    def __format__(self, spec: str) -> str:
        return format(str(self), spec)

    def __hash__(self):
        return self._idx

    def __eq__(self, other):
        return self is other


class _AilIntEnum(_AilEnum):
    def __str__(self) -> str:
        return str(self.value)

    def __hash__(self):
        return self.value

    def _ail_en_int_operand(self, other, op: str, reverse: bool):
        # CPython compares and combines an IntEnum / IntFlag with another int subclass by value;
        # any other Enum member is a plain object (its own __eq__ is identity), not an int.
        if isinstance(other, _AilIntEnum):
            return other.value
        if isinstance(other, _AilEnum):
            if reverse:
                raise TypeError("unsupported operand type(s) for " + op + ": '" + other.cname
                                + "' and '" + self.cname + "'")
            raise TypeError("unsupported operand type(s) for " + op + ": '" + self.cname
                            + "' and '" + other.cname + "'")
        return other

    def _ail_en_int_compare(self, other, op: str, reverse: bool):
        if isinstance(other, _AilIntEnum):
            return other.value
        if isinstance(other, _AilEnum):
            if reverse:
                raise TypeError("'" + op + "' not supported between instances of '" + other.cname
                                + "' and '" + self.cname + "'")
            raise TypeError("'" + op + "' not supported between instances of '" + self.cname
                            + "' and '" + other.cname + "'")
        return other

    def __eq__(self, other):
        if isinstance(other, _AilIntEnum):
            return self.value == other.value
        if isinstance(other, _AilEnum):
            return False
        return self.value == other

    def __lt__(self, other):
        return self.value < self._ail_en_int_compare(other, '<', False)

    def __gt__(self, other):
        return self.value > self._ail_en_int_compare(other, '>', False)

    def __le__(self, other):
        return self.value <= self._ail_en_int_compare(other, '<=', False)

    def __ge__(self, other):
        return self.value >= self._ail_en_int_compare(other, '>=', False)

    def __bool__(self) -> bool:
        return self.value != 0

    def __format__(self, spec: str) -> str:
        return format(self.value, spec)

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
        return self.value + self._ail_en_int_operand(other, '+', False)

    def __radd__(self, other):
        return self._ail_en_int_operand(other, '+', True) + self.value

    def __sub__(self, other):
        return self.value - self._ail_en_int_operand(other, '-', False)

    def __rsub__(self, other):
        return self._ail_en_int_operand(other, '-', True) - self.value

    def __mul__(self, other):
        return self.value * self._ail_en_int_operand(other, '*', False)

    def __rmul__(self, other):
        return self._ail_en_int_operand(other, '*', True) * self.value

    def __truediv__(self, other):
        return self.value / self._ail_en_int_operand(other, '/', False)

    def __rtruediv__(self, other):
        return self._ail_en_int_operand(other, '/', True) / self.value

    def __floordiv__(self, other):
        return self.value // self._ail_en_int_operand(other, '//', False)

    def __rfloordiv__(self, other):
        return self._ail_en_int_operand(other, '//', True) // self.value

    def __mod__(self, other):
        return self.value % self._ail_en_int_operand(other, '%', False)

    def __rmod__(self, other):
        return self._ail_en_int_operand(other, '%', True) % self.value

    def __pow__(self, other):
        return self.value ** self._ail_en_int_operand(other, '** or pow()', False)

    def __rpow__(self, other):
        return self._ail_en_int_operand(other, '** or pow()', True) ** self.value

    def __lshift__(self, other):
        return self.value << self._ail_en_int_operand(other, '<<', False)

    def __rlshift__(self, other):
        return self._ail_en_int_operand(other, '<<', True) << self.value

    def __rshift__(self, other):
        return self.value >> self._ail_en_int_operand(other, '>>', False)

    def __rrshift__(self, other):
        return self._ail_en_int_operand(other, '>>', True) >> self.value

    def __and__(self, other):
        return self.value & self._ail_en_int_operand(other, '&', False)

    def __rand__(self, other):
        return self._ail_en_int_operand(other, '&', True) & self.value

    def __or__(self, other):
        return self.value | self._ail_en_int_operand(other, '|', False)

    def __ror__(self, other):
        return self._ail_en_int_operand(other, '|', True) | self.value

    def __xor__(self, other):
        return self.value ^ self._ail_en_int_operand(other, '^', False)

    def __rxor__(self, other):
        return self._ail_en_int_operand(other, '^', True) ^ self.value

    def __invert__(self):
        return ~self.value


class _AilStrEnum(_AilEnum):
    def __str__(self) -> str:
        return self.value

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if isinstance(other, _AilStrEnum):
            return self.value == other.value
        if isinstance(other, _AilEnum):
            return False
        return self.value == other

    def __lt__(self, other):
        if isinstance(other, _AilStrEnum):
            return self.value < other.value
        if isinstance(other, _AilEnum):
            raise TypeError("'<' not supported between instances of '" + self.cname
                            + "' and '" + other.cname + "'")
        return self.value < other

    def __gt__(self, other):
        if isinstance(other, _AilStrEnum):
            return self.value > other.value
        if isinstance(other, _AilEnum):
            raise TypeError("'>' not supported between instances of '" + self.cname
                            + "' and '" + other.cname + "'")
        return self.value > other

    def __add__(self, other):
        return self.value + other

    def __radd__(self, other):
        return other + self.value

    def __len__(self) -> int:
        return len(self.value)
