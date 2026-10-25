# task: Compute the frequency of each sum across all 36 outcomes of rolling two six-sided dice and print the distribution.
from collections import Counter
from itertools import product


def main() -> None:
    faces: range = range(1, 7)
    sums: Counter[int] = Counter(a + b for a, b in product(faces, faces))
    total: int = sum(sums.values())

    print("Distribution of sums for two six-sided dice")
    print(f"Total outcomes: {total}")
    print()
    for s in range(2, 13):
        count: int = sums[s]
        probability: float = count / total
        bar: str = "#" * count
        print(f"{s:2d}: {count:2d} ({probability:6.2%}) {bar}")


if __name__ == "__main__":
    main()
