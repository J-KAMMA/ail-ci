import random


def main() -> None:
    random.seed(101)
    prizes = ["pen", "mug", "hat", "book"]
    cumulative = [50, 70, 90, 100]
    for index in range(6):
        print(index, random.choices(prizes, cum_weights=cumulative, k=1)[0])
    winners = random.choices(prizes, cum_weights=cumulative, k=5)
    print("winners", winners)
    print("relative", random.choices(prizes, weights=[50, 20, 20, 10], k=3))


main()
