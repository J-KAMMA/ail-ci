# task: Simulate sandpile avalanche toppling on a 15x15 grid with a single central pile of 1000 grains and print the number of cells that toppled at least once.
from typing import Final


GRID_SIZE: Final[int] = 15
THRESHOLD: Final[int] = 4
INITIAL_GRAINS: Final[int] = 1000
NEIGHBORS: Final[tuple[tuple[int, int], ...]] = ((-1, 0), (1, 0), (0, -1), (0, 1))


def stabilize(grid: list[list[int]]) -> set[tuple[int, int]]:
    """Topple the sandpile until stable and return the set of cells that toppled."""
    n = len(grid)
    toppled: set[tuple[int, int]] = set()
    stack: list[tuple[int, int]] = [
        (r, c)
        for r in range(n)
        for c in range(n)
        if grid[r][c] >= THRESHOLD
    ]

    while stack:
        r, c = stack.pop()
        if grid[r][c] < THRESHOLD:
            continue

        # Toppling a cell k times at once is equivalent to k single topplings
        # (the sandpile model is abelian), so the final state is identical.
        k = grid[r][c] // THRESHOLD
        grid[r][c] -= THRESHOLD * k
        toppled.add((r, c))

        for dr, dc in NEIGHBORS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n:
                grid[nr][nc] += k
                if grid[nr][nc] >= THRESHOLD:
                    stack.append((nr, nc))
            # Grains moving off the edge are lost to the sink.

    return toppled


def main() -> None:
    grid: list[list[int]] = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
    center: int = GRID_SIZE // 2
    grid[center][center] = INITIAL_GRAINS

    toppled_cells = stabilize(grid)
    print(len(toppled_cells))


if __name__ == "__main__":
    main()
