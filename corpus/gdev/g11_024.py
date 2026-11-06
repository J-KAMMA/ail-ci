# task: Compute the perimeter of the union of a fixed set of rectangles placed on a 12x12 grid and print the result.
from typing import Final

GRID_SIZE: Final[int] = 12

# Each rectangle is (x1, y1, x2, y2) with half-open ranges:
# columns x1..x2-1 and rows y1..y2-1 on the 12x12 grid.
RECTANGLES: Final[tuple[tuple[int, int, int, int], ...]] = (
    (0, 0, 4, 3),
    (2, 2, 6, 5),
    (8, 1, 11, 4),
    (5, 7, 9, 10),
    (10, 8, 12, 12),
    (0, 9, 3, 12),
)

Cell = tuple[int, int]


def validate_rectangle(rect: tuple[int, int, int, int]) -> None:
    """Raise ValueError if a rectangle is empty or leaves the grid."""
    x1, y1, x2, y2 = rect
    if not (0 <= x1 < x2 <= GRID_SIZE and 0 <= y1 < y2 <= GRID_SIZE):
        raise ValueError(f"rectangle {rect} is invalid for a {GRID_SIZE}x{GRID_SIZE} grid")


def build_union(rects: tuple[tuple[int, int, int, int], ...]) -> set[Cell]:
    """Return the set of all grid cells covered by at least one rectangle."""
    cells: set[Cell] = set()
    for rect in rects:
        validate_rectangle(rect)
        x1, y1, x2, y2 = rect
        for x in range(x1, x2):
            for y in range(y1, y2):
                cells.add((x, y))
    return cells


def union_perimeter(cells: set[Cell]) -> int:
    """Count unit edges between a covered cell and an uncovered cell or the outside."""
    total = 0
    for x, y in cells:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in cells:
                total += 1
    return total


def main() -> None:
    cells = build_union(RECTANGLES)
    perimeter = union_perimeter(cells)
    print(f"Covered cells: {len(cells)}")
    print(f"Perimeter of union: {perimeter}")


if __name__ == "__main__":
    main()
