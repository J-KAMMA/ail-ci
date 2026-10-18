import random
import sys


def main() -> None:
    data = sys.stdin.read().split()
    seed = int(data[0])
    n = int(data[1])

    rng = random.Random(seed)

    position = 0
    maximum = 0
    minimum = 0

    for _ in range(n):
        position += rng.choice([-1, 1])
        if position > maximum:
            maximum = position
        if position < minimum:
            minimum = position

    print(position)
    print(maximum)
    print(minimum)


if __name__ == "__main__":
    main()
