# task: Compute e by summing the Taylor series until the next term is smaller than 1e-16, and print the result alongside math.e.
import math


def compute_e(threshold: float = 1e-16) -> tuple[float, int]:
    """Sum the Taylor series for e = sum(1/k!) until the next term is below threshold.

    Returns the approximation and the number of terms added after the initial 1.
    """
    total: float = 1.0  # k = 0 term
    term: float = 1.0
    k: int = 0
    while True:
        k += 1
        term /= k  # term is now 1/k!
        if term < threshold:
            break
        total += term
    return total, k - 1


def main() -> None:
    approx, terms = compute_e()
    print(f"Taylor series approximation of e: {approx!r}")
    print(f"math.e:                           {math.e!r}")
    print(f"Absolute difference:              {abs(approx - math.e):.3e}")
    print(f"Terms added after k=0:            {terms}")


if __name__ == "__main__":
    main()
