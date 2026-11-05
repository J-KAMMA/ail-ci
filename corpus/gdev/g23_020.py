# task: Compute the matrix power A^n for a hard-coded 2x2 matrix and a fixed exponent using repeated multiplication and print the result.
from typing import List

Matrix = List[List[int]]


def mat_mul(a: Matrix, b: Matrix) -> Matrix:
    """Multiply two 2x2 matrices."""
    return [
        [
            a[0][0] * b[0][0] + a[0][1] * b[1][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1],
        ],
        [
            a[1][0] * b[0][0] + a[1][1] * b[1][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1],
        ],
    ]


def mat_pow(base: Matrix, exponent: int) -> Matrix:
    """Compute base^exponent by repeated multiplication."""
    result: Matrix = [[1, 0], [0, 1]]  # identity matrix
    for _ in range(exponent):
        result = mat_mul(result, base)
    return result


def format_matrix(m: Matrix) -> str:
    """Format a 2x2 matrix as aligned rows."""
    width = max(len(str(x)) for row in m for x in row)
    return "\n".join(
        "[ " + "  ".join(str(x).rjust(width) for x in row) + " ]" for row in m
    )


def main() -> None:
    a: Matrix = [[1, 2], [3, 4]]
    n: int = 5

    power = mat_pow(a, n)

    print(f"A =")
    print(format_matrix(a))
    print(f"A^{n} =")
    print(format_matrix(power))


if __name__ == "__main__":
    main()
