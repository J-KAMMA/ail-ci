# task: Estimate the standard error of the median of a fixed sample using seeded bootstrap resampling with 2000 replicates.
import random
import statistics

SEED: int = 20240607
N_REPLICATES: int = 2000
SAMPLE: list[float] = [
    12.1, 9.8, 11.4, 10.2, 13.7, 8.9, 10.9, 12.6, 11.1, 9.5,
    14.2, 10.7, 11.8, 9.9, 12.3, 10.4, 13.1, 11.6, 10.0, 12.8,
]


def bootstrap_medians(sample: list[float], n_replicates: int, rng: random.Random) -> list[float]:
    """Return the median of each bootstrap resample drawn with replacement."""
    n: int = len(sample)
    medians: list[float] = []
    for _ in range(n_replicates):
        resample: list[float] = rng.choices(sample, k=n)
        medians.append(statistics.median(resample))
    return medians


def estimate_se_of_median(sample: list[float], n_replicates: int, seed: int) -> tuple[float, float, list[float]]:
    """Estimate the standard error of the sample median via the bootstrap.

    Returns (observed median, bootstrap standard error, bootstrap medians).
    """
    rng = random.Random(seed)
    boot: list[float] = bootstrap_medians(sample, n_replicates, rng)
    se: float = statistics.stdev(boot)
    observed: float = statistics.median(sample)
    return observed, se, boot


def main() -> None:
    observed, se, boot = estimate_se_of_median(SAMPLE, N_REPLICATES, SEED)
    sorted_boot: list[float] = sorted(boot)
    lower: float = sorted_boot[int(0.025 * len(sorted_boot))]
    upper: float = sorted_boot[int(0.975 * len(sorted_boot)) - 1]

    print(f"Sample size:            {len(SAMPLE)}")
    print(f"Bootstrap replicates:   {N_REPLICATES}")
    print(f"Random seed:            {SEED}")
    print(f"Observed median:        {observed:.4f}")
    print(f"Bootstrap mean median:  {statistics.fmean(boot):.4f}")
    print(f"Bootstrap SE of median: {se:.4f}")
    print(f"95% percentile CI:      [{lower:.4f}, {upper:.4f}]")


if __name__ == "__main__":
    main()
