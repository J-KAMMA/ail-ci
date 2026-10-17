import sys
from itertools import product

MOD = 1_000_000_007


def count_valid(n: int) -> int:
    """Number of binary strings of length n with no two consecutive 1s."""
    a, b = 1, 2  # a: count for length 0, b: count for length 1
    for _ in range(n - 1):
        a, b = b, (a + b) % MOD
    return b


def valid_strings(n: int) -> list[str]:
    return [
        "".join(bits)
        for bits in product("01", repeat=n)
        if "11" not in "".join(bits)
    ]


def main() -> None:
    n = int(sys.stdin.readline())
    print(count_valid(n) % MOD)
    for s in valid_strings(min(n, 4)):
        print(s)


if __name__ == "__main__":
    main()
