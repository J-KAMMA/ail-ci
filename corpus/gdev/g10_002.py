# task: Write a script that computes the unweighted shortest path length between two fixed nodes in a hardcoded grid-shaped graph using BFS.
from collections import deque
from typing import Optional


ROWS: int = 6
COLS: int = 8

# Hardcoded obstacle cells as (row, col); these cells are impassable.
WALLS: frozenset[tuple[int, int]] = frozenset({
    (0, 2), (1, 2), (2, 2), (3, 2),
    (1, 5), (2, 5), (3, 5), (4, 5),
    (5, 1), (5, 2), (4, 1),
    (2, 0), (3, 6),
})

START: tuple[int, int] = (0, 0)
GOAL: tuple[int, int] = (5, 7)


def neighbors(cell: tuple[int, int]) -> list[tuple[int, int]]:
    """Return the 4-directional, in-bounds, non-wall neighbors of a cell.

    Neighbor order is fixed (up, down, left, right) for determinism.
    """
    r, c = cell
    result: list[tuple[int, int]] = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in WALLS:
            result.append((nr, nc))
    return result


def bfs_shortest_path_length(
    start: tuple[int, int], goal: tuple[int, int]
) -> Optional[int]:
    """Return the number of edges on the shortest path from start to goal, or None."""
    if start == goal:
        return 0

    visited: set[tuple[int, int]] = {start}
    queue: deque[tuple[tuple[int, int], int]] = deque([(start, 0)])

    while queue:
        cell, dist = queue.popleft()
        for nxt in neighbors(cell):
            if nxt in visited:
                continue
            if nxt == goal:
                return dist + 1
            visited.add(nxt)
            queue.append((nxt, dist + 1))
    return None


def render_grid() -> str:
    """Return an ASCII rendering of the grid for human inspection."""
    lines: list[str] = []
    for r in range(ROWS):
        row_chars: list[str] = []
        for c in range(COLS):
            if (r, c) == START:
                row_chars.append("S")
            elif (r, c) == GOAL:
                row_chars.append("G")
            elif (r, c) in WALLS:
                row_chars.append("#")
            else:
                row_chars.append(".")
        lines.append("".join(row_chars))
    return "\n".join(lines)


def main() -> None:
    print("Grid:")
    print(render_grid())
    print(f"Start: {START}")
    print(f"Goal:  {GOAL}")
    length: Optional[int] = bfs_shortest_path_length(START, GOAL)
    if length is None:
        print("No path exists between start and goal.")
    else:
        print(f"Shortest path length: {length}")


if __name__ == "__main__":
    main()
