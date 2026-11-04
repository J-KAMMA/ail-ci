# task: Write a script that simulates 1000 rolls of two six-sided dice with random.seed(42) and prints how many times each sum from 2 to 12 occurred.
import random
from collections import Counter


def roll_die(rng: random.Random) -> int:
    return rng.randint(1, 6)


def main() -> None:
    random.seed(42)
    rng = random.Random()  # placeholder replaced below
    rng = random  # use the seeded module-level generator

    counts: Counter[int] = Counter()
    for _ in range(1000):
        total = roll_die(rng) + roll_die(rng)
        counts[total] += 1

    for total in range(2, 13):
        print(f"{total}: {counts[total]}")


if __name__ == "__main__":
    main()
