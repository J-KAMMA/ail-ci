import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    h, w = int(data[0]), int(data[1])
    rows = data[2:2 + h]

    grid = [[int(ch) for ch in row] for row in rows]

    out = []

    for r in range(h):
        out.append(str(sum(grid[r])))

    for c in range(w):
        out.append(str(sum(grid[r][c] for r in range(h))))

    n = min(h, w)
    main_diag = sum(grid[i][i] for i in range(n))
    anti_diag = sum(grid[i][w - 1 - i] for i in range(n))
    out.append(str(main_diag))
    out.append(str(anti_diag))

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
