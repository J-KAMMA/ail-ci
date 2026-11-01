# task: Compute the exact mean of a fixed dataset using fractions.Fraction and print its difference from the floating-point mean.
from fractions import Fraction
from typing import Sequence

DATA: tuple[float, ...] = (
    0.1,
    0.2,
    0.3,
    0.4,
    0.7,
    1e16,
    1.0,
    -1e16,
    0.1,
    0.25,
)


def exact_mean(values: Sequence[float]) -> Fraction:
    """Return the arithmetic mean of values as an exact Fraction."""
    total = sum((Fraction(v) for v in values), Fraction(0))
    return total / len(values)


def float_mean(values: Sequence[float]) -> float:
    """Return the arithmetic mean computed with ordinary floating-point arithmetic."""
    return sum(values) / len(values)


def main() -> None:
    exact = exact_mean(DATA)
    approx = float_mean(DATA)
    diff = Fraction(approx) - exact

    print(f"count: {len(DATA)}")
    print(f"exact mean: {exact} ~= {float(exact)!r}")
    print(f"float mean: {approx!r}")
    print(f"difference (float - exact): {diff} ~= {float(diff)!r}")


if __name__ == "__main__":
    main()
