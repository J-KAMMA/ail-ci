import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    it = iter(data)
    n = int(next(it))
    grid = [[int(next(it)) for _ in range(n)] for _ in range(n)]

    row_min = [min(row) for row in grid]
    col_max = [max(grid[i][j] for i in range(n)) for j in range(n)]

    result: list[tuple[int, int]] = []
    for i in range(n):
        for j in range(n):
            if grid[i][j] == row_min[i] and grid[i][j] == col_max[j]:
                result.append((i + 1, j + 1))

    out = [str(len(result))]
    out.extend(f"{i} {j}" for i, j in result)
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
