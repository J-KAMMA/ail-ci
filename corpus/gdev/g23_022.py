# task: Rotate a hard-coded 2D point list of coordinates by 90 degrees using a rotation matrix and print the rotated points.
from typing import Final, Sequence

Point = tuple[int, int]

# 90-degree counterclockwise rotation matrix.
# Using exact integers avoids floating-point error from cos(pi/2) and sin(pi/2).
ROTATION_90_CCW: Final[tuple[tuple[int, int], tuple[int, int]]] = (
    (0, -1),
    (1, 0),
)

POINTS: Final[list[Point]] = [
    (1, 0),
    (2, 3),
    (-4, 5),
    (0, -2),
    (6, 6),
]


def rotate_point(point: Point, matrix: tuple[tuple[int, int], tuple[int, int]]) -> Point:
    """Apply a 2x2 matrix to a 2D point and return the transformed point."""
    x, y = point
    (a, b), (c, d) = matrix
    return (a * x + b * y, c * x + d * y)


def rotate_points(points: Sequence[Point], matrix: tuple[tuple[int, int], tuple[int, int]]) -> list[Point]:
    """Rotate every point in the sequence using the given matrix."""
    return [rotate_point(p, matrix) for p in points]


def main() -> None:
    rotated: list[Point] = rotate_points(POINTS, ROTATION_90_CCW)

    print("Original points:")
    for i, p in enumerate(POINTS):
        print(f"  {i}: {p}")

    print("Rotated 90 degrees counterclockwise:")
    for i, p in enumerate(rotated):
        print(f"  {i}: {p}")


if __name__ == "__main__":
    main()
