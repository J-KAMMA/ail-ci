# task: Write a script that computes the Cartesian product of two hardcoded sets and prints the number of resulting pairs and the sorted pairs.
from itertools import product


def main() -> None:
    set_a: set[str] = {"banana", "apple", "cherry"}
    set_b: set[int] = {3, 1, 2}

    pairs: list[tuple[str, int]] = sorted(product(set_a, set_b))

    print(f"Number of pairs: {len(pairs)}")
    print("Sorted pairs:")
    for pair in pairs:
        print(pair)


if __name__ == "__main__":
    main()
