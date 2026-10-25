# task: Build an identity matrix of size 5 using nested lists and print it row by row.
from __future__ import annotations


def identity_matrix(size: int) -> list[list[int]]:
    """Return an identity matrix of the given size as nested lists."""
    return [[1 if row == col else 0 for col in range(size)] for row in range(size)]


def main() -> None:
    matrix: list[list[int]] = identity_matrix(5)
    for row in matrix:
        print(" ".join(str(value) for value in row))


if __name__ == "__main__":
    main()
