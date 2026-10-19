import sys


def main() -> None:
    data = sys.stdin.read().split()
    h = int(data[0])
    w = int(data[1])
    grid: list[str] = data[2:2 + h]

    # Locate S and E by scanning the grid (S is top-left and E bottom-right per spec).
    start: tuple[int, int] | None = None
    end: tuple[int, int] | None = None
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == 'S':
                start = (r, c)
            elif ch == 'E':
                end = (r, c)

    if start is None:
        print(0)
        print("no")
        return

    def passable(r: int, c: int) -> bool:
        return 0 <= r < len(grid) and 0 <= c < len(grid[r]) and grid[r][c] != '#'

    visited: set[tuple[int, int]] = {start}
    stack: list[tuple[int, int]] = [start]
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

    while stack:
        r, c = stack.pop()
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if (nr, nc) not in visited and passable(nr, nc):
                visited.add((nr, nc))
                stack.append((nr, nc))

    e_reachable = end is not None and end in visited

    print(len(visited))
    print("yes" if e_reachable else "no")


if __name__ == "__main__":
    main()
