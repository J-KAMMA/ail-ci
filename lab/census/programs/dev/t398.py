import random
import sys


def estimate_pi(seed: int, n: int) -> float:
    rng = random.Random(seed)
    total = n * 100
    inside = 0
    for _ in range(total):
        x = rng.random()
        y = rng.random()
        if x * x + y * y <= 1.0:
            inside += 1
    if total == 0:
        return 0.0
    return 4.0 * inside / total


def main() -> None:
    data = sys.stdin.read().split()
    seed = int(data[0])
    n = int(data[1])
    print(f"{estimate_pi(seed, n):.4f}")


if __name__ == "__main__":
    main()
