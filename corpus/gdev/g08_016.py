# task: Recursively compute the Ackermann function for small inputs A(2, 3) and A(3, 3) and print the results.
import sys


def ackermann(m: int, n: int) -> int:
    """Recursively compute the Ackermann function A(m, n)."""
    if m == 0:
        return n + 1
    if n == 0:
        return ackermann(m - 1, 1)
    return ackermann(m - 1, ackermann(m, n - 1))


def main() -> None:
    sys.setrecursionlimit(10_000)

    a23: int = ackermann(2, 3)
    a33: int = ackermann(3, 3)

    print(f"A(2, 3) = {a23}")
    print(f"A(3, 3) = {a33}")


if __name__ == "__main__":
    main()
