# task: Compare naive summation with Kahan compensated summation for one million additions of 0.1 and print the error of each.
from fractions import Fraction


def naive_sum(value: float, count: int) -> float:
    """Add `value` to a running total `count` times, with plain floating-point addition."""
    total: float = 0.0
    for _ in range(count):
        total += value
    return total


def kahan_sum(value: float, count: int) -> float:
    """Add `value` to a running total `count` times, using Kahan compensated summation."""
    total: float = 0.0
    compensation: float = 0.0
    for _ in range(count):
        y: float = value - compensation
        t: float = total + y
        compensation = (t - total) - y
        total = t
    return total


def main() -> None:
    value: float = 0.1
    count: int = 1_000_000

    # The exact sum of the double-precision value 0.1 added one million times.
    exact: Fraction = Fraction(value) * count

    naive: float = naive_sum(value, count)
    kahan: float = kahan_sum(value, count)

    naive_error: float = float(Fraction(naive) - exact)
    kahan_error: float = float(Fraction(kahan) - exact)

    print(f"Adding {value!r} {count:,} times")
    print(f"Exact sum (of the float 0.1):  {float(exact)!r}")
    print()
    print(f"Naive summation:  {naive!r}")
    print(f"  error: {naive_error:.6e}")
    print()
    print(f"Kahan summation:  {kahan!r}")
    print(f"  error: {kahan_error:.6e}")


if __name__ == "__main__":
    main()
