import sys
from itertools import product

MOD = 1_000_000_007


def count_strings(n: int) -> int:
    prev, curr = 1, 2
    if n == 0:
        return prev
    for _ in range(2, n + 1):
        prev, curr = curr, (prev + curr) % MOD
    return curr % MOD


def valid_strings(length: int) -> list[str]:
    return [
        "".join(bits)
        for bits in product("01", repeat=length)
        if "11" not in "".join(bits)
    ]


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])

    lines = [str(count_strings(n))]
    lines.extend(valid_strings(min(n, 4)))
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
