# task: Solve a hard-coded 9x9 Sudoku puzzle with recursive backtracking and print the completed grid.
from typing import Optional

PUZZLE: list[list[int]] = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]


def find_empty(grid: list[list[int]]) -> Optional[tuple[int, int]]:
    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                return (r, c)
    return None


def is_valid(grid: list[list[int]], row: int, col: int, value: int) -> bool:
    if value in grid[row]:
        return False
    if any(grid[r][col] == value for r in range(9)):
        return False
    box_row, box_col = (row // 3) * 3, (col // 3) * 3
    for r in range(box_row, box_row + 3):
        for c in range(box_col, box_col + 3):
            if grid[r][c] == value:
                return False
    return True


def solve(grid: list[list[int]]) -> bool:
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


def format_grid(grid: list[list[int]]) -> str:
    lines: list[str] = []
    for r in range(9):
        if r % 3 == 0 and r != 0:
            lines.append("------+-------+------")
        parts: list[str] = []
        for c in range(9):
            if c % 3 == 0 and c != 0:
                parts.append("|")
            parts.append(str(grid[r][c]))
        lines.append(" ".join(parts))
    return "\n".join(lines)


def main() -> None:
    grid: list[list[int]] = [row[:] for row in PUZZLE]
    if solve(grid):
        print(format_grid(grid))
    else:
        print("No solution exists.")


if __name__ == "__main__":
    main()
