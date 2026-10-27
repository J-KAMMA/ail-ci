# task: Convert the integers 0 through 15 to Gray code and back to binary, printing any round-trip mismatches.
from typing import Final


def to_gray(n: int) -> int:
    """Convert a non-negative integer to its reflected Gray code."""
    return n ^ (n >> 1)


def from_gray(g: int) -> int:
    """Convert a reflected Gray code value back to binary."""
    n = 0
    while g:
        n ^= g
        g >>= 1
    return n


def main() -> None:
    lo: Final[int] = 0
    hi: Final[int] = 15
    mismatches: list[tuple[int, int, int]] = []

    for value in range(lo, hi + 1):
        gray = to_gray(value)
        back = from_gray(gray)
        print(f"{value:2d} -> gray {gray:04b} ({gray:2d}) -> binary {back:2d}")
        if back != value:
            mismatches.append((value, gray, back))

    if mismatches:
        print("Round-trip mismatches:")
        for value, gray, back in mismatches:
            print(f"  input {value}, gray {gray:04b}, decoded {back}")
    else:
        print("No round-trip mismatches found.")


if __name__ == "__main__":
    main()
