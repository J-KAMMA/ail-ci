# task: Write a script that computes the set difference A minus B for two hardcoded integer sets and prints the sorted output.
from typing import Set


def compute_difference(a: Set[int], b: Set[int]) -> list[int]:
    """Return the sorted elements of a that are not in b (A - B)."""
    return sorted(a - b)


def main() -> None:
    A: Set[int] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
    B: Set[int] = {2, 4, 6, 8, 10, 12, 14}

    result = compute_difference(A, B)
    print(" ".join(str(x) for x in result))


if __name__ == "__main__":
    main()
