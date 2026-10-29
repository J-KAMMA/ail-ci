# task: Find the shortest path between two fixed corners of a hard-coded 10x10 grid with walls using breadth-first search and print the path length.
from collections import deque

GRID: list[str] = [
    "..........",
    "#####.###.",
    "....#...#.",
    ".##.#.#.#.",
    ".#..#.#...",
    ".#.##.#.##",
    ".#....#...",
    ".####.###.",
    "......#...",
    "###.##....",
]

START: tuple[int, int] = (0, 0)
GOAL: tuple[int, int] = (9, 9)


def in_bounds(row: int, col: int) -> bool:
    return 0 <= row < len(GRID) and 0 <= col < len(GRID[0])


def is_open(row: int, col: int) -> bool:
    return GRID[row][col] == "."


def shortest_path_length(start: tuple[int, int], goal: tuple[int, int]) -> int | None:
    """Return the number of steps on the shortest path, or None if unreachable."""
    if not is_open(*start) or not is_open(*goal):
        return None

    distances: dict[tuple[int, int], int] = {start: 0}
    queue: deque[tuple[int, int]] = deque([start])
    directions: tuple[tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

    while queue:
        row, col = queue.popleft()
        if (row, col) == goal:
            return distances[(row, col)]
        for d_row, d_col in directions:
            next_row, next_col = row + d_row, col + d_col
            neighbor = (next_row, next_col)
            if (
                in_bounds(next_row, next_col)
                and is_open(next_row, next_col)
                and neighbor not in distances
            ):
                distances[neighbor] = distances[(row, col)] + 1
                queue.append(neighbor)

    return None


def main() -> None:
    length: int | None = shortest_path_length(START, GOAL)
    if length is None:
        print(f"No path from {START} to {GOAL}.")
    else:
        print(f"Shortest path length from {START} to {GOAL}: {length}")


if __name__ == "__main__":
    main()
