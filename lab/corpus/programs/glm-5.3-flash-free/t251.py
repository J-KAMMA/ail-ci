import sys
from itertools import starmap

Matrix = list[list[int]]


def mat_mult(a: Matrix, b: Matrix) -> Matrix:
    bt = list(zip(*b))
    return [[sum(x * y for x, y in zip(row, col)) for col in bt] for row in a]


def mat_pow(a: Matrix, e: int) -> Matrix:
    n = len(a)
    result = [[1 if i == j else 0 for j in range(n)] for i in range(n)]
    base = a
    while e > 0:
        if e & 1:
            result = mat_mult(result, base)
        base = mat_mult(base, base)
        e >>= 1
    return result


def main() -> None:
    data = sys.stdin.read().split()
    it = iter(data)
    n = int(next(it))
    a = [[int(next(it)) for _ in range(n)] for _ in range(n)]
    e = int(next(it))
    res = mat_pow(a, e)
    out = "\n".join(" ".join(map(str, row)) for row in res)
    print(out)


if __name__ == "__main__":
    main()
