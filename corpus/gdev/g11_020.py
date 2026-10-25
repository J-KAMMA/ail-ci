# task: Simulate a forest fire cellular automaton on a 20x20 grid with fixed initial pattern for 40 steps and print the number of burning cells at the end.
from typing import Final

SIZE: Final[int] = 20
STEPS: Final[int] = 40

EMPTY: Final[int] = 0
TREE: Final[int] = 1
BURNING: Final[int] = 2

Grid = list[list[int]]


def initial_grid() -> Grid:
    """Build the fixed initial forest pattern with a partial firebreak."""
    grid: Grid = [[EMPTY] * SIZE for _ in range(SIZE)]
    for y in range(SIZE):
        for x in range(SIZE):
            if (x * 7 + y * 3) % 5 != 0:
                grid[y][x] = TREE
    # Firebreak column at x == 10, with gaps (bridges) every 7th row.
    for y in range(SIZE):
        if y % 7 != 3:
            grid[y][10] = EMPTY
    # Fixed ignition points (both are tree cells).
    grid[0][1] = BURNING
    grid[10][1] = BURNING
    return grid


def has_burning_neighbor(grid: Grid, x: int, y: int) -> bool:
    """Return True if any 4-connected neighbor of (x, y) is burning."""
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < SIZE and 0 <= ny < SIZE and grid[ny][nx] == BURNING:
            return True
    return False


def step(grid: Grid) -> Grid:
    """Advance the forest fire automaton by one synchronous step."""
    new_grid: Grid = [[EMPTY] * SIZE for _ in range(SIZE)]
    for y in range(SIZE):
        for x in range(SIZE):
            state = grid[y][x]
            if state == BURNING:
                new_grid[y][x] = EMPTY
            elif state == TREE:
                if has_burning_neighbor(grid, x, y):
                    new_grid[y][x] = BURNING
                else:
                    new_grid[y][x] = TREE
            else:
                new_grid[y][x] = EMPTY
    return new_grid


def count_burning(grid: Grid) -> int:
    """Count the number of burning cells in the grid."""
    return sum(1 for row in grid for cell in row if cell == BURNING)


def main() -> None:
    grid = initial_grid()
    for _ in range(STEPS):
        grid = step(grid)
    print(count_burning(grid))


if __name__ == "__main__":
    main()
