# task: Use recursive backtracking to count all paths through a fixed 5x5 maze from start to exit and print the count.
from typing import Final

MAZE: Final[tuple[str, ...]] = (
    "S....",
    ".#.#.",
    ".#.#.",
    ".#...",
    "...#E",
)

DIRECTIONS: Final[tuple[tuple[int, int], ...]] = ((-1, 0), (1, 0), (0, -1), (0, 1))


def find_cell(grid: tuple[str, ...], symbol: str) -> tuple[int, int]:
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == symbol:
                return (r, c)
    raise ValueError(f"symbol {symbol!r} not found in maze")


def is_open(grid: tuple[str, ...], r: int, c: int) -> bool:
    return 0 <= r < len(grid) and 0 <= c < len(grid[r]) and grid[r][c] != "#"


def count_paths(
    grid: tuple[str, ...],
    pos: tuple[int, int],
    exit_pos: tuple[int, int],
    visited: set[tuple[int, int]],
) -> int:
    """Count simple paths from pos to exit_pos using recursive backtracking."""
    if pos == exit_pos:
        return 1

    total = 0
    r, c = pos
    for dr, dc in DIRECTIONS:
        nr, nc = r + dr, c + dc
        nxt = (nr, nc)
        if is_open(grid, nr, nc) and nxt not in visited:
            visited.add(nxt)
            total += count_paths(grid, nxt, exit_pos, visited)
            visited.remove(nxt)  # backtrack
    return total


def main() -> None:
    start = find_cell(MAZE, "S")
    exit_pos = find_cell(MAZE, "E")
    visited: set[tuple[int, int]] = {start}
    paths = count_paths(MAZE, start, exit_pos, visited)
    print(f"Maze size: {len(MAZE)}x{len(MAZE[0])}")
    print(f"Start: {start}, Exit: {exit_pos}")
    print(f"Number of paths from start to exit: {paths}")


if __name__ == "__main__":
    main()
