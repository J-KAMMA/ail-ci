import random
import sys


def main() -> None:
    data = sys.stdin.read().split()
    seed = int(data[0])
    n = int(data[1])

    rng = random.Random(seed)
    position = 0
    max_position = 0
    min_position = 0

    for _ in range(n):
        position += rng.choice([-1, 1])
        if position > max_position:
            max_position = position
        if position < min_position:
            min_position = position

    print(position, max_position, min_position)


if __name__ == "__main__":
    main()
