# task: Simulate the Ising model on a 16x16 grid with a fixed seed using Metropolis updates for 200 sweeps and print the final magnetization rounded to three decimals.
import math
import random


SIZE: int = 16
SWEEPS: int = 200
BETA: float = 0.4406868  # near critical inverse temperature (2 / ln(1 + sqrt(2)))
SEED: int = 12345


def initial_lattice(rng: random.Random, n: int) -> list[list[int]]:
    """Create an n x n lattice with random +1/-1 spins."""
    return [[rng.choice((-1, 1)) for _ in range(n)] for _ in range(n)]


def neighbor_sum(lattice: list[list[int]], i: int, j: int, n: int) -> int:
    """Sum of the four nearest neighbors with periodic boundaries."""
    return (
        lattice[(i - 1) % n][j]
        + lattice[(i + 1) % n][j]
        + lattice[i][(j - 1) % n]
        + lattice[i][(j + 1) % n]
    )


def metropolis_sweep(
    lattice: list[list[int]],
    rng: random.Random,
    beta: float,
    n: int,
) -> None:
    """Perform one Metropolis sweep: n*n single-spin update attempts."""
    acceptance: dict[int, float] = {
        dE: math.exp(-beta * dE) for dE in (4, 8)
    }
    for _ in range(n * n):
        i = rng.randrange(n)
        j = rng.randrange(n)
        s = lattice[i][j]
        dE = 2 * s * neighbor_sum(lattice, i, j, n)
        if dE <= 0 or rng.random() < acceptance[dE]:
            lattice[i][j] = -s


def magnetization(lattice: list[list[int]]) -> float:
    """Average spin per site."""
    total = sum(sum(row) for row in lattice)
    return total / (len(lattice) * len(lattice[0]))


def main() -> None:
    rng = random.Random(SEED)
    random.seed(SEED)
    lattice = initial_lattice(rng, SIZE)
    for _ in range(SWEEPS):
        metropolis_sweep(lattice, rng, BETA, SIZE)
    m = magnetization(lattice)
    print(f"{m:.3f}")


if __name__ == "__main__":
    main()
