# task: Estimate pi with a seeded Monte Carlo simulation that samples random points in a unit square and counts those inside the quarter circle.
import random


def estimate_pi(samples: int, seed: int) -> float:
    """Estimate pi by sampling points in the unit square and counting
    those that fall inside the quarter circle of radius 1."""
    rng = random.Random(seed)
    inside = 0
    for _ in range(samples):
        x = rng.random()
        y = rng.random()
        if x * x + y * y <= 1.0:
            inside += 1
    return 4.0 * inside / samples


def main() -> None:
    seed = 42
    sample_counts = [1_000, 10_000, 100_000, 1_000_000]
    random.seed(seed)  # seed the global generator as well, for determinism
    print("Monte Carlo estimation of pi (quarter-circle method)")
    print(f"Seed: {seed}")
    for n in sample_counts:
        estimate = estimate_pi(n, seed)
        error = abs(estimate - 3.141592653589793)
        print(f"samples={n:>9,d}  estimate={estimate:.6f}  abs_error={error:.6f}")


if __name__ == "__main__":
    main()
