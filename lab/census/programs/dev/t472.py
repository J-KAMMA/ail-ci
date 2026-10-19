import math
import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    numbers: list[int] = [int(tok) for tok in data[1:1 + n]]

    first = numbers[:8]
    magnitudes: list[int] = [abs(v) for v in first]

    # Per-value math functions on |v| + 1 (always >= 1, so log2 is defined).
    for v in first:
        a = abs(v) + 1
        print(
            f"{v}: sqrt={math.sqrt(a):.3f} "
            f"log2={math.log2(a):.3f} "
            f"sin={math.sin(a):.3f} "
            f"cos={math.cos(a):.3f}"
        )

    # Aggregate functions over the absolute values of the first 8 numbers.
    print(f"hypot: {math.hypot(*magnitudes):.3f}")
    print(f"gcd: {math.gcd(*magnitudes)}")
    print(f"isqrt: {math.isqrt(sum(magnitudes))}")


if __name__ == "__main__":
    main()
