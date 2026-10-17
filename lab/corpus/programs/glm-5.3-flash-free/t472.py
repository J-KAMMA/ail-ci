import math
import sys


def read_ints() -> list[int]:
    data = sys.stdin.read().split()
    n = int(data[0])
    return [int(t) for t in data[1:1 + n]]


def main() -> None:
    xs = read_ints()
    vals = [abs(x) + 1 for x in xs[:8]]
    for v in vals:
        print(f"{math.sqrt(v):.3f} {math.log2(v):.3f} {math.sin(v):.3f} {math.cos(v):.3f}")
    if vals:
        print(f"{math.hypot(*vals):.3f}")
        print(math.gcd(*vals))
        print(math.isqrt(vals[0]))


if __name__ == "__main__":
    main()
