# task: Solve a hard-coded 3x3 linear system Ax=b using Cramer's rule and print the solution vector.
from fractions import Fraction


def det3(m: list[list[Fraction]]) -> Fraction:
    """Return the determinant of a 3x3 matrix using cofactor expansion along the first row."""
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def replace_column(a: list[list[Fraction]], col: int, b: list[Fraction]) -> list[list[Fraction]]:
    """Return a copy of matrix a with column `col` replaced by vector b."""
    result = [row[:] for row in a]
    for i in range(3):
        result[i][col] = b[i]
    return result


def cramer_solve(a: list[list[Fraction]], b: list[Fraction]) -> list[Fraction]:
    """Solve Ax = b for a 3x3 system using Cramer's rule with exact arithmetic."""
    d = det3(a)
    if d == 0:
        raise ValueError("Matrix is singular (determinant is zero); Cramer's rule does not apply.")
    solution: list[Fraction] = []
    for col in range(3):
        d_i = det3(replace_column(a, col, b))
        solution.append(d_i / d)
    return solution


def main() -> None:
    A: list[list[Fraction]] = [
        [Fraction(2), Fraction(1), Fraction(-1)],
        [Fraction(-3), Fraction(-1), Fraction(2)],
        [Fraction(-2), Fraction(1), Fraction(2)],
    ]
    b: list[Fraction] = [Fraction(8), Fraction(-11), Fraction(-3)]

    print("Coefficient matrix A:")
    for row in A:
        print("  ", [str(v) for v in row])
    print("Right-hand side b:", [str(v) for v in b])
    print("det(A) =", det3(A))

    x = cramer_solve(A, b)
    print("Solution vector x:")
    for i, value in enumerate(x):
        print(f"  x{i + 1} = {value}")
    print("x =", [str(v) for v in x])


if __name__ == "__main__":
    main()
