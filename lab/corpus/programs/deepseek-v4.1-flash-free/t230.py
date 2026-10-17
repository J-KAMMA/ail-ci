import sys


def step(grid: list[list[str]], h: int, w: int) -> list[list[str]]:
    new = [["." for _ in range(w)] for _ in range(h)]
    for r in range(h):
        for c in range(w):
            neighbors = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr = (r + dr) % h
                    cc = (c + dc) % w
                    if grid[rr][cc] == "#":
                        neighbors += 1
            alive = grid[r][c] == "#"
            if alive and neighbors in (2, 3):
                new[r][c] = "#"
            elif not alive and neighbors == 3:
                new[r][c] = "#"
    return new


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    h = int(data[0])
    w = int(data[1])
    grid = [list(row) for row in data[2:2 + h]] if h else []
    for _ in range(4):
        grid = step(grid, h, w)
    live = sum(row.count("#") for row in grid)
    out = ["".join(row) for row in grid]
    out.append(str(live))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
