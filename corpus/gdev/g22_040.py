# task: Enumerate all 8-bit integers with exactly three set bits in increasing order using Gosper's hack and print them.
from typing import Iterator


def gosper_next(x: int) -> int:
    """Return the next integer with the same number of set bits as x (Gosper's hack)."""
    c = x & -x
    r = x + c
    return (((r ^ x) >> 2) // c) | r


def combinations_of_bits(width: int, k: int) -> Iterator[int]:
    """Yield all integers in [0, 2**width) with exactly k set bits, in increasing order."""
    if k == 0:
        yield 0
        return
    if k > width:
        return
    x = (1 << k) - 1
    limit = 1 << width
    while x < limit:
        yield x
        x = gosper_next(x)


def main() -> None:
    width = 8
    bits = 3
    count = 0
    for value in combinations_of_bits(width, bits):
        count += 1
        print(f"{value:3d}  0b{value:08b}")
    print(f"Total: {count}")


if __name__ == "__main__":
    main()
