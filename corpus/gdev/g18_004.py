# task: Define a namedtuple Point with x and y fields, compute Manhattan distances from the origin for hardcoded points, and print the farthest one.
from collections import namedtuple
from typing import List

Point = namedtuple("Point", ["x", "y"])


def manhattan_from_origin(p: Point) -> int:
    """Return the Manhattan distance of a point from the origin (0, 0)."""
    return abs(p.x) + abs(p.y)


def farthest_point(points: List[Point]) -> Point:
    """Return the point with the greatest Manhattan distance from the origin.

    On ties, the first point in the list wins, so the result is deterministic.
    """
    return max(points, key=manhattan_from_origin)


def main() -> None:
    points: List[Point] = [
        Point(1, 2),
        Point(-4, 3),
        Point(0, 0),
        Point(5, -6),
        Point(-2, -2),
        Point(3, 7),
    ]

    for p in points:
        print(f"Point(x={p.x}, y={p.y}) -> distance {manhattan_from_origin(p)}")

    far = farthest_point(points)
    print(
        f"Farthest point: Point(x={far.x}, y={far.y}) "
        f"with distance {manhattan_from_origin(far)}"
    )


if __name__ == "__main__":
    main()
