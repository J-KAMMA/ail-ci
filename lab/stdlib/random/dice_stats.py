import random


def main() -> None:
    random.seed(2024)
    counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    rolls = 600
    total = 0
    for _ in range(rolls):
        face = random.randint(1, 6)
        counts[face] = counts[face] + 1
        total = total + face
    for face in range(1, 7):
        n = counts[face]
        print(face, n, "%.1f%%" % (100.0 * n / rolls))
    print("total", total, "mean", "%.3f" % (total / rolls))


main()
