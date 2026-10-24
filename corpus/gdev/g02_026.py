# task: Compute the sum-of-divisors function σ(n) for n up to 10,000 and print the n with the largest σ(n)/n.
def compute_sigma_table(limit: int) -> list[int]:
    """Return a list where index n holds sigma(n), the sum of divisors of n, for 0 <= n <= limit."""
    sigma: list[int] = [0] * (limit + 1)
    for d in range(1, limit + 1):
        for multiple in range(d, limit + 1, d):
            sigma[multiple] += d
    return sigma


def find_max_abundancy(limit: int, sigma: list[int]) -> tuple[int, int]:
    """Return (n, sigma(n)) maximizing sigma(n)/n for 1 <= n <= limit.

    Ties are resolved in favor of the smallest n. Comparisons use exact
    integer cross-multiplication rather than floating point.
    """
    best_n = 1
    best_sigma = sigma[1]
    for n in range(2, limit + 1):
        # sigma[n] / n > best_sigma / best_n  <=>  sigma[n] * best_n > best_sigma * n
        if sigma[n] * best_n > best_sigma * n:
            best_n = n
            best_sigma = sigma[n]
    return best_n, best_sigma


def main() -> None:
    limit: int = 10_000
    sigma = compute_sigma_table(limit)
    n, s = find_max_abundancy(limit, sigma)
    print(f"n = {n}")
    print(f"sigma(n) = {s}")
    print(f"sigma(n)/n = {s}/{n} ≈ {s / n:.6f}")


if __name__ == "__main__":
    main()
