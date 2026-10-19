import math
import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    a: int = int(data[0])
    b: int = int(data[1])

    g: int = math.gcd(a, b)
    l: int = a // g * b
    coprime: bool = g == 1

    print(g)
    print(l)
    print(coprime)


if __name__ == "__main__":
    main()
