# task: Compute the centroid of a hard-coded list of 2D points using vector averaging and print it.
from typing import Sequence


Point = tuple[float, float]


def centroid(points: Sequence[Point]) -> Point:
    """Return the centroid (arithmetic mean position) of a non-empty sequence of 2D points."""
    if not points:
        raise ValueError("centroid requires at least one point")
    n = len(points)
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    return (sum_x / n, sum_y / n)


def main() -> None:
    points: list[Point] = [
        (1.0, 2.0),
        (3.0, 8.0),
        (-4.0, 5.0),
        (6.5, -1.5),
        (0.0, 0.0),
        (2.5, 4.0),
    ]
    cx, cy = centroid(points)
    print(f"Centroid of {len(points)} points: ({cx:.4f}, {cy:.4f})")


if __name__ == "__main__":
    main()
