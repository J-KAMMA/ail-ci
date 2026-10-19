import sys


def main() -> None:
    data = sys.stdin.read().split()
    r = int(data[0])
    c = int(data[1])
    vals = list(map(int, data[2:2 + r * c]))

    a: list[list[int]] = [vals[i * c:(i + 1) * c] for i in range(r)]

    # Transpose: c x r
    t: list[list[int]] = [[a[i][j] for i in range(r)] for j in range(c)]

    # Product A * A^T: r x r
    p: list[list[int]] = [
        [sum(a[i][k] * a[j][k] for k in range(c)) for j in range(r)]
        for i in range(r)
    ]

    lines = [" ".join(map(str, row)) for row in t]
    lines += [" ".join(map(str, row)) for row in p]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
