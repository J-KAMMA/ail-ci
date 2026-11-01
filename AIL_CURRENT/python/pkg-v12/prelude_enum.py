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

    def __divmod__(self, other):
        if isinstance(other, _AilEnum):
            return (self.value // other.value, self.value % other.value)
        return (self.value // other, self.value % other)

    def __rdivmod__(self, other):
        if isinstance(other, _AilEnum):
            return (other.value // self.value, other.value % self.value)
        return (other // self.value, other % self.value)

    def __lshift__(self, other):
        if isinstance(other, _AilEnum):
            return self.value << other.value
        return self.value << other

    def __rlshift__(self, other):
        return other << self.value

    def __rshift__(self, other):
        if isinstance(other, _AilEnum):
            return self.value >> other.value
        return self.value >> other

    def __rrshift__(self, other):
        return other >> self.value

    def __and__(self, other):
        if isinstance(other, _AilEnum):
            return self.value & other.value
        return self.value & other

    def __rand__(self, other):
        return other & self.value

    def __or__(self, other):
        if isinstance(other, _AilEnum):
            return self.value | other.value
        return self.value | other

    def __ror__(self, other):
        return other | self.value

    def __xor__(self, other):
        if isinstance(other, _AilEnum):
            return self.value ^ other.value
        return self.value ^ other

    def __rxor__(self, other):
        return other ^ self.value

    def __invert__(self):
        return ~self.value

    def __pow__(self, other):
        if isinstance(other, _AilEnum):
            return self.value ** other.value
        return self.value ** other

    def __rpow__(self, other):
        return other ** self.value


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

    def __le__(self, other):
        if isinstance(other, _AilEnum):
            return self.value <= other.value
        return self.value <= other

    def __ge__(self, other):
        if isinstance(other, _AilEnum):
            return self.value >= other.value
        return self.value >= other

    def __add__(self, other):
        return self.value + other

    def __radd__(self, other):
        return other + self.value

    def __mul__(self, other):
        if isinstance(other, _AilEnum):
            return self.value * other.value
        return self.value * other

    def __rmul__(self, other):
        return other * self.value

    def __contains__(self, item):
        return item in self.value

    def __getitem__(self, index):
        return self.value[index]

    def __len__(self) -> int:
        return len(self.value)

    def upper(self) -> str:
        return self.value.upper()

    def lower(self) -> str:
        return self.value.lower()

    def title(self) -> str:
        return self.value.title()

    def capitalize(self) -> str:
        return self.value.capitalize()

    def casefold(self) -> str:
        return self.value.casefold()

    def swapcase(self) -> str:
        return self.value.swapcase()

    def strip(self, chars=None) -> str:
        if chars is None:
            return self.value.strip()
        return self.value.strip(chars)

    def lstrip(self, chars=None) -> str:
        if chars is None:
            return self.value.lstrip()
        return self.value.lstrip(chars)

    def rstrip(self, chars=None) -> str:
        if chars is None:
            return self.value.rstrip()
        return self.value.rstrip(chars)

    def startswith(self, prefix, start=0, end=None) -> bool:
        if end is None:
            if start == 0:
                return self.value.startswith(prefix)
            return self.value.startswith(prefix, start)
        return self.value.startswith(prefix, start, end)

    def endswith(self, suffix, start=0, end=None) -> bool:
        if end is None:
            if start == 0:
                return self.value.endswith(suffix)
            return self.value.endswith(suffix, start)
        return self.value.endswith(suffix, start, end)

    def find(self, sub, start=0, end=None) -> int:
        if end is None:
            if start == 0:
                return self.value.find(sub)
            return self.value.find(sub, start)
        return self.value.find(sub, start, end)

    def rfind(self, sub, start=0, end=None) -> int:
        if end is None:
            if start == 0:
                return self.value.rfind(sub)
            return self.value.rfind(sub, start)
        return self.value.rfind(sub, start, end)

    def index(self, sub, start=0, end=None) -> int:
        if end is None:
            if start == 0:
                return self.value.index(sub)
            return self.value.index(sub, start)
        return self.value.index(sub, start, end)

    def rindex(self, sub, start=0, end=None) -> int:
        if end is None:
            if start == 0:
                return self.value.rindex(sub)
            return self.value.rindex(sub, start)
        return self.value.rindex(sub, start, end)

    def count(self, sub, start=0, end=None) -> int:
        if end is None:
            if start == 0:
                return self.value.count(sub)
            return self.value.count(sub, start)
        return self.value.count(sub, start, end)

    def replace(self, old: str, new: str, count: int = -1) -> str:
        return self.value.replace(old, new, count)

    def removeprefix(self, prefix: str) -> str:
        return self.value.removeprefix(prefix)

    def removesuffix(self, suffix: str) -> str:
        return self.value.removesuffix(suffix)

    def split(self, sep=None, maxsplit: int = -1) -> list[str]:
        if maxsplit == -1:
            if sep is None:
                return self.value.split()
            return self.value.split(sep)
        return self.value.split(sep, maxsplit)

    def rsplit(self, sep=None, maxsplit: int = -1) -> list[str]:
        if maxsplit == -1:
            if sep is None:
                return self.value.rsplit()
            return self.value.rsplit(sep)
        return self.value.rsplit(sep, maxsplit)

    def splitlines(self, keepends: bool = False) -> list[str]:
        return self.value.splitlines(keepends)

    def join(self, items: list[str]) -> str:
        return self.value.join(items)

    def partition(self, sep: str) -> tuple[str, str, str]:
        return self.value.partition(sep)

    def rpartition(self, sep: str) -> tuple[str, str, str]:
        return self.value.rpartition(sep)

    def zfill(self, width: int) -> str:
        return self.value.zfill(width)

    def center(self, width: int, fillchar: str = " ") -> str:
        return self.value.center(width, fillchar)

    def ljust(self, width: int, fillchar: str = " ") -> str:
        return self.value.ljust(width, fillchar)

    def rjust(self, width: int, fillchar: str = " ") -> str:
        return self.value.rjust(width, fillchar)

    def isdigit(self) -> bool:
        return self.value.isdigit()

    def isalpha(self) -> bool:
        return self.value.isalpha()

    def isalnum(self) -> bool:
        return self.value.isalnum()

    def isspace(self) -> bool:
        return self.value.isspace()

    def isupper(self) -> bool:
        return self.value.isupper()

    def islower(self) -> bool:
        return self.value.islower()

    def isnumeric(self) -> bool:
        return self.value.isnumeric()

    def isdecimal(self) -> bool:
        return self.value.isdecimal()

    def isidentifier(self) -> bool:
        return self.value.isidentifier()

    def isascii(self) -> bool:
        return self.value.isascii()
