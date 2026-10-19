import random
import sys


def main() -> None:
    data = sys.stdin.read().split()
    seed = int(data[0])
    n = int(data[1])

    rng = random.Random(seed)
    interarrival = 2
    teller_free_at = 0
    total_wait = 0

    for i in range(n):
        arrival = i * interarrival
        service = rng.randint(1, 5)
        start = max(arrival, teller_free_at)
        total_wait += start - arrival
        teller_free_at = start + service

    average = total_wait / n if n > 0 else 0.0
    print(f"{average:.3f}")


if __name__ == "__main__":
    main()
