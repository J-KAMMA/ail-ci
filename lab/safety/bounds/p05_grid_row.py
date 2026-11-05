def row_total(grid: list[list[int]], row: int) -> int:
    return sum(grid[row])


grid: list[list[int]] = [[1, 2], [3, 4]]
print("rows", len(grid))
print("row 1 total", row_total(grid, 1))
print("row 0", grid[0])
print("row past", grid[len(grid)][0])
