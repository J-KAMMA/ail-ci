import sys


def main() -> None:
    data = sys.stdin.read().split()
    h = int(data[0])
    w = int(data[1])
    grid: list[list[int]] = []
    idx = 2
    for _ in range(h):
        row = [int(ch) for ch in data[idx]]
        grid.append(row)
        idx += 1

    out: list[str] = []
    for r in range(h):
        out.append(str(sum(grid[r])))
    for c in range(w):
        out.append(str(sum(grid[r][c] for r in range(h))))
    out.append(str(sum(grid[i][i] for i in range(h))))
    out.append(str(sum(grid[i][w - 1 - i] for i in range(h))))

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
