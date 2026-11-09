# task: Compute the geometric mean and harmonic mean of a fixed list of positive floats and verify that the arithmetic mean is at least the geometric mean.
import math
import statistics
from collections.abc import Sequence

DATA: tuple[float, ...] = (
    1.5,
    2.25,
    3.0,
    0.75,
    10.0,
    4.5,
    6.125,
    2.0,
    0.5,
    8.0,
)


def validate_positive(values: Sequence[float]) -> None:
    """Raise ValueError unless every value is a finite, strictly positive number."""
    if not values:
        raise ValueError("data must not be empty")
    for v in values:
        if not math.isfinite(v) or v <= 0.0:
            raise ValueError(f"all values must be finite and positive, got {v!r}")


def arithmetic_mean(values: Sequence[float]) -> float:
    """Arithmetic mean computed with exact-rounded summation."""
    return math.fsum(values) / len(values)


def geometric_mean(values: Sequence[float]) -> float:
    """Geometric mean (the n-th root of the product), via the statistics module."""
    return statistics.geometric_mean(values)


def harmonic_mean(values: Sequence[float]) -> float:
    """Harmonic mean: n divided by the sum of reciprocals."""
    return statistics.harmonic_mean(values)


def is_at_least(a: float, b: float, rel_tol: float = 1e-12) -> bool:
    """Return True if a >= b up to a small relative tolerance."""
    return a >= b or math.isclose(a, b, rel_tol=rel_tol, abs_tol=0.0)


def main() -> None:
    data = list(DATA)
    validate_positive(data)

    am = arithmetic_mean(data)
    gm = geometric_mean(data)
    hm = harmonic_mean(data)

    print(f"Count:              {len(data)}")
    print(f"Arithmetic mean:    {am:.10f}")
    print(f"Geometric mean:     {gm:.10f}")
    print(f"Harmonic mean:      {hm:.10f}")

    am_ge_gm = is_at_least(am, gm)
    gm_ge_hm = is_at_least(gm, hm)

    print(f"AM >= GM:           {am_ge_gm}")
    print(f"GM >= HM:           {gm_ge_hm}")

    if am_ge_gm and gm_ge_hm:
        print("Verification: PASSED (AM >= GM >= HM)")
    else:
        print("Verification: FAILED")


if __name__ == "__main__":
    main()
