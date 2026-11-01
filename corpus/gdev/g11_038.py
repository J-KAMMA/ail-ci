# task: Compute the convex hull of a fixed set of grid points on a 10x10 grid using Andrew's monotone chain algorithm and print the hull vertices.
from collections.abc import Sequence

Point = tuple[int, int]

# Fixed point set on a 10x10 grid (coordinates 0..9).
POINTS: list[Point] = [
    (0, 0), (3, 0), (6, 1), (9, 0), (9, 4), (8, 7), (9, 9), (5, 8),
    (2, 9), (0, 9), (1, 5), (0, 3), (4, 4), (3, 6), (6, 5), (5, 2),
    (7, 3), (2, 2), (4, 8), (7, 7), (1, 8), (8, 2), (3, 3), (6, 9),
]


def cross(o: Point, a: Point, b: Point) -> int:
    """Z-component of (a - o) x (b - o); positive means a left turn."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points: Sequence[Point]) -> list[Point]:
    """Andrew's monotone chain. Returns hull vertices in counterclockwise order,
    starting from the lexicographically smallest point, without collinear points."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    # Drop the last point of each chain; it is the first point of the other.
    return lower[:-1] + upper[:-1]


def polygon_area2(vertices: Sequence[Point]) -> int:
    """Twice the signed area of a polygon (shoelace formula)."""
    total = 0
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total


def main() -> None:
    hull = convex_hull(POINTS)

    print(f"Input points: {len(set(POINTS))}")
    print(f"Hull vertices: {len(hull)}")
    print("Vertices (counterclockwise):")
    for x, y in hull:
        print(f"  ({x}, {y})")
    print(f"Hull area: {polygon_area2(hull) / 2:.1f}")


if __name__ == "__main__":
    main()
