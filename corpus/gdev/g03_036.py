# task: Solve a fixed 3 by 3 linear system with Gaussian elimination using partial pivoting and print the solution vector.
from typing import List


def gauss_solve(a: List[List[float]], b: List[float]) -> List[float]:
    """Solve a @ x = b using Gaussian elimination with partial pivoting."""
    n = len(b)
    # Build augmented matrix [A | b] as a copy so inputs are not modified.
    m: List[List[float]] = [row[:] + [b[i]] for i, row in enumerate(a)]

    for col in range(n):
        # Partial pivoting: choose the row with the largest absolute value in this column.
        pivot_row = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot_row][col]) < 1e-12:
            raise ValueError("matrix is singular or nearly singular")
        m[col], m[pivot_row] = m[pivot_row], m[col]

        # Eliminate entries below the pivot.
        for r in range(col + 1, n):
            factor = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]

    # Back substitution.
    x: List[float] = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = sum(m[i][j] * x[j] for j in range(i + 1, n))
        x[i] = (m[i][n] - s) / m[i][i]
    return x


def main() -> None:
    # Fixed system; the first pivot is zero, so pivoting is required.
    # Exact solution: x = (2, 3, -1).
    a: List[List[float]] = [
        [0.0, 2.0, 1.0],
        [1.0, -2.0, -3.0],
        [-1.0, 1.0, 2.0],
    ]
    b: List[float] = [5.0, -1.0, -1.0]

    x = gauss_solve(a, b)

    print("Solution vector:")
    for i, value in enumerate(x):
        print(f"x{i + 1} = {value:.6f}")


if __name__ == "__main__":
    main()
