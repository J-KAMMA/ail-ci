import sys


def step(grid: list[list[bool]], h: int, w: int) -> list[list[bool]]:
    """Advance one generation on a torus (wrap-around grid)."""
    new_grid = [[False] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            neighbors = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    if grid[(r + dr) % h][(c + dc) % w]:
                        neighbors += 1
            alive = grid[r][c]
            new_grid[r][c] = neighbors == 3 or (alive and neighbors == 2)
    return new_grid


def main() -> None:
    tokens = sys.stdin.read().split()
    h = int(tokens[0])
    w = int(tokens[1])
    rows = tokens[2:2 + h]

    grid: list[list[bool]] = [
        [ch == "#" for ch in row[:w].ljust(w, ".")]
        for row in rows
    ]
    while len(grid) < h:
        grid.append([False] * w)

    for _ in range(4):
        grid = step(grid, h, w)

    lines = []
    live = 0
    for row in grid:
        lines.append("".join("#" if cell else "." for cell in row))
        live += sum(row)

    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.write(f"{live}\n")


if __name__ == "__main__":
    main()
