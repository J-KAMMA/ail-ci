import sys


def main() -> None:
    data = sys.stdin.read().split()
    h, w = int(data[0]), int(data[1])
    grid: list[str] = data[2:2 + h]

    # Transpose: the result has w rows, each of length h.
    transposed: list[str] = [
        "".join(grid[r][c] for r in range(h)) for c in range(w)
    ]

    # Rotate the transposed grid 90 degrees clockwise.
    # Row i of the result is column i of the transposed grid, read bottom to top.
    rows_t = len(transposed)
    cols_t = len(transposed[0]) if rows_t else 0
    rotated: list[str] = [
        "".join(transposed[rows_t - 1 - j][i] for j in range(rows_t))
        for i in range(cols_t)
    ]

    for line in transposed:
        print(line)
    for line in rotated:
        print(line)


if __name__ == "__main__":
    main()
