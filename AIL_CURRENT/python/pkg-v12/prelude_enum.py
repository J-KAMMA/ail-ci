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
        # object.__eq__: the other operand's __eq__ is tried next, then identity
        return True if self is other else NotImplemented


class _AilIntEnum(_AilEnum):
    def __str__(self) -> str:
        return str(self.value)

    def __hash__(self):
        return self.value

    def _ail_en_num(self, other):
        # an IntEnum/IntFlag peer is its value; another enum kind is a different type. Builtin numbers and
        # Decimal/Fraction keep the int-subclass dispatch, so the underlying int operation (or the other
        # operand's reflected method) sees it; any other object is asked next, as int does. Sequences are
        # deliberately absent: only multiplication may consume them (see _ail_en_mul), so that other
        # operators keep int's NotImplemented and the TypeError names the enum class.
        if isinstance(other, _AilIntEnum):
            return other.value
        if isinstance(other, _AilEnum):
            return NotImplemented
        if isinstance(other, (int, float)):
            return other
        try:
            if hasattr(other, "_ail_dec") or hasattr(other, "_ail_fr"):
                return other
        except NotImplementedError:
            pass
        return NotImplemented

    def _ail_en_mul(self, other):
        # like _ail_en_num, plus the builtin sequences that support repetition. `range` is excluded because
        # CPython has no `range * int` either; leaving it out makes the error name the enum class.
        if isinstance(other, _AilIntEnum):
            return other.value
        if isinstance(other, _AilEnum):
            return NotImplemented
        if isinstance(other, (int, float, str, bytes, bytearray, list, tuple)):
            return other
        try:
            if hasattr(other, "_ail_dec") or hasattr(other, "_ail_fr"):
                return other
        except NotImplementedError:
            pass
        return NotImplemented

    def _ail_en_bits(self, other):
        # like _ail_en_num but only an int operand: <<, >>, &, | and ^ reject a float
        if isinstance(other, _AilIntEnum):
            return other.value
        if isinstance(other, _AilEnum):
            return NotImplemented
        if isinstance(other, int):
            return other
        return NotImplemented

    def __eq__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value == v

    def __lt__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value < v

    def __gt__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value > v

    def __le__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value <= v

    def __ge__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value >= v

    def __bool__(self) -> bool:
        return self.value != 0

    def __format__(self, spec: str) -> str:
        return format(self.value, spec)

    def __int__(self) -> int:
        return self.value

    def __index__(self) -> int:
        return int(self.value)

    def __float__(self) -> float:
        return float(self.value)

    def __neg__(self):
        return -self.value

    def __abs__(self):
        return abs(self.value)

    def __add__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value + v

    def __radd__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return v + self.value

    def __sub__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value - v

    def __rsub__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return v - self.value

    def __mul__(self, other):
        v = self._ail_en_mul(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value * v

    def __rmul__(self, other):
        v = self._ail_en_mul(other)
        if v is NotImplemented:
            return NotImplemented
        return v * self.value

    def __truediv__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value / v

    def __rtruediv__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return v / self.value

    def __floordiv__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value // v

    def __rfloordiv__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return v // self.value

    def __mod__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value % v

    def __rmod__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return v % self.value

    def __pow__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value ** v

    def __rpow__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return v ** self.value

    def __divmod__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return (self.value // v, self.value % v)

    def __rdivmod__(self, other):
        v = self._ail_en_num(other)
        if v is NotImplemented:
            return NotImplemented
        return (v // self.value, v % self.value)

    def __lshift__(self, other):
        v = self._ail_en_bits(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value << v

    def __rlshift__(self, other):
        v = self._ail_en_bits(other)
        if v is NotImplemented:
            return NotImplemented
        return v << self.value

    def __rshift__(self, other):
        v = self._ail_en_bits(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value >> v

    def __rrshift__(self, other):
        v = self._ail_en_bits(other)
        if v is NotImplemented:
            return NotImplemented
        return v >> self.value

    def __and__(self, other):
        v = self._ail_en_bits(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value & v

    def __rand__(self, other):
        v = self._ail_en_bits(other)
        if v is NotImplemented:
            return NotImplemented
        return v & self.value

    def __or__(self, other):
        v = self._ail_en_bits(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value | v

    def __ror__(self, other):
        v = self._ail_en_bits(other)
        if v is NotImplemented:
            return NotImplemented
        return v | self.value

    def __xor__(self, other):
        v = self._ail_en_bits(other)
        if v is NotImplemented:
            return NotImplemented
        return self.value ^ v

    def __rxor__(self, other):
        v = self._ail_en_bits(other)
        if v is NotImplemented:
            return NotImplemented
        return v ^ self.value

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
        if isinstance(other, _AilEnum) or not isinstance(other, str):
            return NotImplemented
        return self.value == other

    def __lt__(self, other):
        if isinstance(other, _AilStrEnum):
            return self.value < other.value
        if isinstance(other, _AilEnum) or not isinstance(other, str):
            return NotImplemented
        return self.value < other

    def __gt__(self, other):
        if isinstance(other, _AilStrEnum):
            return self.value > other.value
        if isinstance(other, _AilEnum) or not isinstance(other, str):
            return NotImplemented
        return self.value > other

    def __add__(self, other):
        return self.value + other

    def __radd__(self, other):
        return other + self.value

    def __len__(self) -> int:
        return len(self.value)
