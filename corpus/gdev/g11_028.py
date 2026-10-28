# task: Simulate a predator-prey cellular grid where foxes and rabbits move randomly with a fixed seed on a 15x15 grid for 30 steps and print the final population counts.
import random
from typing import Final

GRID_SIZE: Final[int] = 15
STEPS: Final[int] = 30
SEED: Final[int] = 42
INITIAL_RABBITS: Final[int] = 40
INITIAL_FOXES: Final[int] = 10

EMPTY: Final[str] = "."
RABBIT: Final[str] = "R"
FOX: Final[str] = "F"

DIRECTIONS: Final[list[tuple[int, int]]] = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def create_grid(rng: random.Random) -> list[list[str]]:
    """Create an empty grid and randomly place the initial animals."""
    grid: list[list[str]] = [[EMPTY] * GRID_SIZE for _ in range(GRID_SIZE)]
    total_cells = GRID_SIZE * GRID_SIZE
    chosen = rng.sample(range(total_cells), INITIAL_RABBITS + INITIAL_FOXES)
    for index, cell in enumerate(chosen):
        row, col = divmod(cell, GRID_SIZE)
        grid[row][col] = RABBIT if index < INITIAL_RABBITS else FOX
    return grid


def animal_positions(grid: list[list[str]]) -> list[tuple[int, int, str]]:
    """Return all animals as (row, col, kind), sorted by position."""
    positions: list[tuple[int, int, str]] = []
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            kind = grid[row][col]
            if kind != EMPTY:
                positions.append((row, col, kind))
    return positions


def step(grid: list[list[str]], rng: random.Random) -> None:
    """Advance the simulation by one step: every animal attempts one random move."""
    for row, col, kind in animal_positions(grid):
        # Skip animals that were eaten earlier in this step.
        if grid[row][col] != kind:
            continue

        dr, dc = rng.choice(DIRECTIONS)
        new_row, new_col = row + dr, col + dc
        if not (0 <= new_row < GRID_SIZE and 0 <= new_col < GRID_SIZE):
            continue

        target = grid[new_row][new_col]
        if target == EMPTY:
            grid[new_row][new_col] = kind
            grid[row][col] = EMPTY
        elif kind == FOX and target == RABBIT:
            # A fox moving onto a rabbit eats it.
            grid[new_row][new_col] = FOX
            grid[row][col] = EMPTY
        # Otherwise the move is blocked (same species, or rabbit into fox).


def count_population(grid: list[list[str]], kind: str) -> int:
    """Count how many cells contain the given kind of animal."""
    return sum(1 for row in grid for cell in row if cell == kind)


def main() -> None:
    random.seed(SEED)
    rng = random.Random(SEED)

    grid = create_grid(rng)
    for _ in range(STEPS):
        step(grid, rng)

    rabbits = count_population(grid, RABBIT)
    foxes = count_population(grid, FOX)
    print(f"After {STEPS} steps on a {GRID_SIZE}x{GRID_SIZE} grid:")
    print(f"Rabbits: {rabbits}")
    print(f"Foxes: {foxes}")


if __name__ == "__main__":
    main()
