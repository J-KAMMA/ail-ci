# task: Implement a small bitset over the range 0 to 63 supporting add, remove, union, and intersection, then print the results of a fixed sequence of operations.
from __future__ import annotations


class BitSet64:
    """A small bitset over the integer range 0..63, stored in a single int."""

    MIN_VALUE: int = 0
    MAX_VALUE: int = 63
    _MASK: int = (1 << 64) - 1

    __slots__ = ("_bits",)

    def __init__(self, values: "list[int] | tuple[int, ...] | None" = None) -> None:
        self._bits: int = 0
        if values is not None:
            for v in values:
                self.add(v)

    @classmethod
    def _check(cls, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"element must be an int, got {type(value).__name__}")
        if not (cls.MIN_VALUE <= value <= cls.MAX_VALUE):
            raise ValueError(f"element {value} out of range {cls.MIN_VALUE}..{cls.MAX_VALUE}")

    def add(self, value: int) -> None:
        self._check(value)
        self._bits |= 1 << value

    def remove(self, value: int) -> None:
        self._check(value)
        self._bits &= ~(1 << value) & self._MASK

    def __contains__(self, value: object) -> bool:
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        if not (self.MIN_VALUE <= value <= self.MAX_VALUE):
            return False
        return bool((self._bits >> value) & 1)

    def union(self, other: "BitSet64") -> "BitSet64":
        result = BitSet64()
        result._bits = self._bits | other._bits
        return result

    def intersection(self, other: "BitSet64") -> "BitSet64":
        result = BitSet64()
        result._bits = self._bits & other._bits
        return result

    def to_list(self) -> list[int]:
        return [i for i in range(self.MIN_VALUE, self.MAX_VALUE + 1) if (self._bits >> i) & 1]

    def __len__(self) -> int:
        return bin(self._bits).count("1")

    def __repr__(self) -> str:
        return f"BitSet64({self.to_list()})"


def main() -> None:
    a = BitSet64()
    for v in (0, 1, 2, 5, 10, 63):
        a.add(v)
    print("a after adds:", a.to_list())

    b = BitSet64([2, 3, 5, 7, 63])
    print("b:", b.to_list())

    a.remove(1)
    print("a after remove(1):", a.to_list())

    u = a.union(b)
    print("a | b:", u.to_list(), "size:", len(u))

    i = a.intersection(b)
    print("a & b:", i.to_list(), "size:", len(i))

    print("contains 5 in a:", 5 in a)
    print("contains 1 in a:", 1 in a)
    print("contains 64 in b:", 64 in b)

    b.remove(63)
    print("b after remove(63):", b.to_list())
    print("a & b after update:", a.intersection(b).to_list())
    print("repr(u):", repr(u))


if __name__ == "__main__":
    main()
