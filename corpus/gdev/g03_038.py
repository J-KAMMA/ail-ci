# task: Simulate many seeded one-dimensional random walks and print the mean and variance of their final displacements.
import random
import statistics


def simulate_walk(steps: int, rng: random.Random) -> int:
    """Return the final displacement of a 1D simple random walk of given length."""
    position: int = 0
    for _ in range(steps):
        position += 1 if rng.random() < 0.5 else -1
    return position


def run_experiment(num_walks: int, steps: int, seed: int) -> list[int]:
    """Simulate num_walks independent walks with a seeded generator."""
    random.seed(seed)
    rng: random.Random = random.Random(seed)
    return [simulate_walk(steps, rng) for _ in range(num_walks)]


def main() -> None:
    num_walks: int = 10_000
    steps: int = 100
    seed: int = 12345

    displacements: list[int] = run_experiment(num_walks, steps, seed)

    mean: float = statistics.fmean(displacements)
    variance: float = statistics.pvariance(displacements)

    print(f"Number of walks: {num_walks}")
    print(f"Steps per walk: {steps}")
    print(f"Seed: {seed}")
    print(f"Mean of final displacements: {mean:.4f}")
    print(f"Variance of final displacements: {variance:.4f}")
    print(f"Theoretical variance (steps): {steps}")


if __name__ == "__main__":
    main()
