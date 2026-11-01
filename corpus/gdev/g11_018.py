# task: Simulate a random walk of 1000 steps on a 2D integer lattice with a fixed seed and print the final position and maximum distance from origin.
import random
import math
from typing import Tuple


def simulate_random_walk(steps: int, seed: int) -> Tuple[Tuple[int, int], float]:
    """Simulate a 2D lattice random walk and return the final position
    and the maximum Euclidean distance from the origin reached."""
    random.seed(seed)
    moves: list[Tuple[int, int]] = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    x, y = 0, 0
    max_distance: float = 0.0

    for _ in range(steps):
        dx, dy = random.choice(moves)
        x += dx
        y += dy
        distance = math.hypot(x, y)
        if distance > max_distance:
            max_distance = distance

    return (x, y), max_distance


def main() -> None:
    steps = 1000
    seed = 42
    final_position, max_distance = simulate_random_walk(steps, seed)
    print(f"Final position: {final_position}")
    print(f"Maximum distance from origin: {max_distance:.4f}")


if __name__ == "__main__":
    main()
