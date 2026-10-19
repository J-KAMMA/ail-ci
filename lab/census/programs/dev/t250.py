import sys


def determinant(matrix: list[list[int]]) -> int:
    """Compute the determinant by Laplace (cofactor) expansion along the first row."""
    n = len(matrix)
    if n == 0:
        return 1
    if n == 1:
        return matrix[0][0]
    total = 0
    for j in range(n):
        minor = [row[:j] + row[j + 1:] for row in matrix[1:]]
        sign = 1 if j % 2 == 0 else -1
        total += sign * matrix[0][j] * determinant(minor)
    return total


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    values = list(map(int, data[1:1 + n * n]))
    matrix: list[list[int]] = [values[i * n:(i + 1) * n] for i in range(n)]

    trace = sum(matrix[i][i] for i in range(n))

    if n <= 6:
        det_text = str(determinant(matrix))
    else:
        det_text = "skip"

    symmetric = all(matrix[i][j] == matrix[j][i] for i in range(n) for j in range(n))

    print(f"Trace: {trace}")
    print(f"Determinant: {det_text}")
    print(f"Symmetric: {'yes' if symmetric else 'no'}")


if __name__ == "__main__":
    main()
