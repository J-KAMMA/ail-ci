import random


def main() -> None:
    random.seed(7)
    pool = list(range(1, 50))
    drawn = random.sample(pool, 5)
    drawn.sort()
    bonus = random.sample(range(1, 13), 1)[0]
    print("numbers", drawn)
    print("bonus", bonus)
    lucky = random.sample(population=pool, k=3)
    print("lucky", sorted(lucky))
    print("quick pick", sorted(random.sample(pool, 5)))


main()
