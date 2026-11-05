# task: Compute the element-wise (Hadamard) product of two hard-coded matrices and print the result.
from typing import List


def hadamard_product(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """Return the element-wise (Hadamard) product of two equally sized matrices."""
    if len(a) != len(b) or any(len(row_a) != len(row_b) for row_a, row_b in zip(a, b)):
        raise ValueError("matrices must have the same dimensions")
    return [[x * y for x, y in zip(row_a, row_b)] for row_a, row_b in zip(a, b)]


def format_matrix(m: List[List[float]]) -> str:
    """Format a matrix as aligned rows of text."""
    return "\n".join("  ".join(f"{value:6.2f}" for value in row) for row in m)


def main() -> None:
    matrix_a: List[List[float]] = [
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
        [7.0, 8.0, 9.0],
    ]
    matrix_b: List[List[float]] = [
        [9.0, 8.0, 7.0],
        [6.0, 5.0, 4.0],
        [3.0, 2.0, 1.0],
    ]

    result = hadamard_product(matrix_a, matrix_b)

    print("Matrix A:")
    print(format_matrix(matrix_a))
    print()
    print("Matrix B:")
    print(format_matrix(matrix_b))
    print()
    print("Hadamard product (A ∘ B):")
    print(format_matrix(result))


if __name__ == "__main__":
    main()
