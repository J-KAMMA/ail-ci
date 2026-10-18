import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    idx = 0
    r = int(data[idx]); idx += 1
    c = int(data[idx]); idx += 1

    a = []
    for _ in range(r):
        row = [int(data[idx + j]) for j in range(c)]
        idx += c
        a.append(row)

    transposed = [[a[i][j] for i in range(r)] for j in range(c)]
    for row in transposed:
        print(" ".join(map(str, row)))

    product = [[sum(a[i][k] * a[j][k] for k in range(c)) for j in range(r)] for i in range(r)]
    for row in product:
        print(" ".join(map(str, row)))


if __name__ == "__main__":
    main()
