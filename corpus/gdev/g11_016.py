# task: Solve a fixed 9x9 Sudoku puzzle using backtracking and print the completed grid.
from typing import Optional


Grid = list[list[int]]

PUZZLE: list[str] = [
    "530070000",
    "600195000",
    "098000060",
    "800060003",
    "400803001",
    "700020006",
    "060000280",
    "000419005",
    "000080079",
]


def parse_grid(rows: list[str]) -> Grid:
    """Convert a list of 9-character strings into a 9x9 integer grid (0 = empty)."""
    if len(rows) != 9 or any(len(r) != 9 for r in rows):
        raise ValueError("Puzzle must be 9 rows of 9 characters each.")
    return [[int(ch) for ch in row] for row in rows]


def find_empty(grid: Grid) -> Optional[tuple[int, int]]:
    """Return the (row, col) of the first empty cell in row-major order, or None."""
    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                return r, c
    return None


def is_valid(grid: Grid, row: int, col: int, value: int) -> bool:
    """Check whether placing value at (row, col) respects Sudoku constraints."""
    if value in grid[row]:
        return False
    if any(grid[r][col] == value for r in range(9)):
        return False
    box_r, box_c = (row // 3) * 3, (col // 3) * 3
    for r in range(box_r, box_r + 3):
        for c in range(box_c, box_c + 3):
            if grid[r][c] == value:
                return False
    return True


def solve(grid: Grid) -> bool:
    """Solve the grid in place using backtracking. Returns True if solved."""
    empty = find_empty(grid)
    if empty is None:
        return True
    row, col = empty
    for value in range(1, 10):
        if is_valid(grid, row, col, value):
            grid[row][col] = value
            if solve(grid):
                return True
            grid[row][col] = 0
    return False


def format_grid(grid: Grid) -> str:
    """Render the grid as text with box separators."""
    lines: list[str] = []
    for r in range(9):
        if r in (3, 6):
            lines.append("------+-------+------")
        parts: list[str] = []
        for c in range(9):
            if c in (3, 6):
                parts.append("|")
            parts.append(str(grid[r][c]))
        lines.append(" ".join(parts))
    return "\n".join(lines)


def main() -> None:
    grid = parse_grid(PUZZLE)
    if solve(grid):
        print(format_grid(grid))
    else:
        print("No solution exists.")


if __name__ == "__main__":
    main()
