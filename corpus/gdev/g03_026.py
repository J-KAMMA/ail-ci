# task: Compute the Poisson probability mass function and cumulative probabilities for lambda equal to 4 up to k equal to 10.
import math


def poisson_pmf(k: int, lam: float) -> float:
    """Return P(X = k) for a Poisson distribution with rate lam."""
    return math.exp(-lam) * lam**k / math.factorial(k)


def poisson_cdf(k: int, lam: float) -> float:
    """Return P(X <= k) for a Poisson distribution with rate lam."""
    return sum(poisson_pmf(i, lam) for i in range(k + 1))


def main() -> None:
    lam: float = 4.0
    max_k: int = 10

    print(f"Poisson distribution with lambda = {lam}")
    print(f"{'k':>3}  {'P(X = k)':>12}  {'P(X <= k)':>12}")
    print("-" * 33)

    for k in range(max_k + 1):
        pmf = poisson_pmf(k, lam)
        cdf = poisson_cdf(k, lam)
        print(f"{k:>3}  {pmf:>12.6f}  {cdf:>12.6f}")


if __name__ == "__main__":
    main()
