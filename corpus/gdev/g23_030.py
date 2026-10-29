# task: Generate a Pascal's triangle as a lower-triangular matrix of size 6 and print it.
from math import comb


def pascal_lower_triangular(size: int) -> list[list[int]]:
    """Return a size x size lower-triangular matrix of Pascal's triangle values."""
    return [[comb(row, col) if col <= row else 0 for col in range(size)]
            for row in range(size)]


def format_matrix(matrix: list[list[int]]) -> str:
    """Format the matrix as right-aligned columns."""
    width = max(len(str(value)) for row in matrix for value in row)
    return "\n".join(
        " ".join(str(value).rjust(width) for value in row)
        for row in matrix
    )


def main() -> None:
    size: int = 6
    matrix = pascal_lower_triangular(size)
    print(format_matrix(matrix))


if __name__ == "__main__":
    main()
