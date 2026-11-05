def column(grid: list[list[int]], col: int) -> list[int]:
    return [row[col] for row in grid]


grid: list[list[int]] = [[1, 2], [3, 4]]
print("width", len(grid[0]))
print("column 1", column(grid, 1))
print("corner", grid[1][1])
print("column past", grid[0][len(grid[0])])
