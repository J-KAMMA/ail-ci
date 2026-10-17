import sys


def mat_mul(a: list[list[int]], b: list[list[int]]) -> list[list[int]]:
    n = len(a)
    result = [[0] * n for _ in range(n)]
    for i in range(n):
        ai = a[i]
        ri = result[i]
        for k in range(n):
            aik = ai[k]
            if aik:
                bk = b[k]
                for j in range(n):
                    ri[j] += aik * bk[j]
    return result


def mat_pow(matrix: list[list[int]], exp: int) -> list[list[int]]:
    n = len(matrix)
    result = [[1 if i == j else 0 for j in range(n)] for i in range(n)]
    base = [row[:] for row in matrix]
    while exp > 0:
        if exp & 1:
            result = mat_mul(result, base)
        exp >>= 1
        if exp:
            base = mat_mul(base, base)
    return result


def main() -> None:
    data = sys.stdin.read().split()
    idx = 0
    n = int(data[idx])
    idx += 1
    matrix = []
    for _ in range(n):
        row = [int(data[idx + j]) for j in range(n)]
        idx += n
        matrix.append(row)
    exp = int(data[idx])

    result = mat_pow(matrix, exp)
    out = "\n".join(" ".join(map(str, row)) for row in result)
    sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
