import random


def main() -> None:
    random.seed(2718)
    position = 0
    high = 0
    low = 0
    steps = []
    for _ in range(40):
        step = random.randrange(-2, 3)
        position = position + step
        steps.append(position)
        high = max(high, position)
        low = min(low, position)
    print("final", position)
    print("high", high, "low", low)
    print("steps", steps)
    print("distance", abs(position))
    even = 0
    for value in steps:
        if value % 2 == 0:
            even = even + 1
    print("even positions", even)


main()
