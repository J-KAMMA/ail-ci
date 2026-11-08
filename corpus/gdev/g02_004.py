# task: Compute the least common multiple of the integers 1 through 20 using gcd and print it.
import math
from functools import reduce


def lcm(a: int, b: int) -> int:
    """Return the least common multiple of two integers."""
    return abs(a * b) // math.gcd(a, b)


def main() -> None:
    result: int = reduce(lcm, range(1, 21), 1)
    print(result)


if __name__ == "__main__":
    main()
