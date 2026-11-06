# task: Compute the sum of the diagonal elements of the product of two hard-coded matrices and print the value.
from typing import List


def matmul(a: List[List[int]], b: List[List[int]]) -> List[List[int]]:
    rows_a = len(a)
    cols_a = len(a[0])
    cols_b = len(b[0])
    result: List[List[int]] = [[0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            total = 0
            for k in range(cols_a):
                total += a[i][k] * b[k][j]
            result[i][j] = total
    return result


def diagonal_sum(m: List[List[int]]) -> int:
    return sum(m[i][i] for i in range(min(len(m), len(m[0]))))


def main() -> None:
    matrix_a: List[List[int]] = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
    ]
    matrix_b: List[List[int]] = [
        [9, 8, 7],
        [6, 5, 4],
        [3, 2, 1],
    ]
    product = matmul(matrix_a, matrix_b)
    print(diagonal_sum(product))


if __name__ == "__main__":
    main()
