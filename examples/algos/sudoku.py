"""Backtracking Sudoku solver for three fixed puzzles."""
import sys

SMALL = "--small" in sys.argv

PUZZLES = [
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079",
    "000000907000420180000705026100904000050000040000507009920108000034059000507000000",
    "030050040008010500460000012070502080000603000040109030250000098001020600080060020",
]
if SMALL:
    PUZZLES = PUZZLES[:1]


def parse(puzzle):
    grid = []
    for row in range(9):
        values = []
        for col in range(9):
            values.append(int(puzzle[row * 9 + col]))
        grid.append(values)
    return grid


def valid(grid, row, col, value):
    for i in range(9):
        if grid[row][i] == value or grid[i][col] == value:
            return False
    base_row = (row // 3) * 3
    base_col = (col // 3) * 3
    for r in range(base_row, base_row + 3):
        for c in range(base_col, base_col + 3):
            if grid[r][c] == value:
                return False
    return True


def find_empty(grid):
    best = None
    best_count = 10
    for row in range(9):
        for col in range(9):
            if grid[row][col] == 0:
                count = 0
                for value in range(1, 10):
                    if valid(grid, row, col, value):
                        count += 1
                if count < best_count:
                    best = (row, col)
                    best_count = count
    return best


def solve(grid):
    empty = find_empty(grid)
    if empty is None:
        return True
    row, col = empty
    for value in range(1, 10):
        if valid(grid, row, col, value):
            grid[row][col] = value
            if solve(grid):
                return True
            grid[row][col] = 0
    return False


for number, puzzle in enumerate(PUZZLES):
    grid = parse(puzzle)
    solved = solve(grid)
    checksum = 0
    for row in range(9):
        for col in range(9):
            checksum += (row + 1) * (col + 1) * grid[row][col]
    print("puzzle", number, "solved", solved, "checksum", checksum)
    print("first row", "".join(str(value) for value in grid[0]))
