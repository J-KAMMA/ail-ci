# task: Sort a list of (name, score) tuples by score descending and name ascending using a single sorted key.
from typing import Sequence


def sort_scores(records: Sequence[tuple[str, int]]) -> list[tuple[str, int]]:
    """Sort (name, score) tuples by score descending, then name ascending."""
    return sorted(records, key=lambda rec: (-rec[1], rec[0]))


def main() -> None:
    data: list[tuple[str, int]] = [
        ("alice", 90),
        ("bob", 85),
        ("carol", 90),
        ("dave", 70),
        ("eve", 85),
        ("frank", 100),
        ("grace", 90),
        ("heidi", 70),
    ]

    ranked = sort_scores(data)
    for name, score in ranked:
        print(f"{name}: {score}")


if __name__ == "__main__":
    main()
