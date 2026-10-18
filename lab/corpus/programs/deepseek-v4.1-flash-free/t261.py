import sys
import math


def polygon_area(points: list[tuple[int, int]]) -> float:
    total = 0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def polygon_perimeter(points: list[tuple[int, int]]) -> float:
    total = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    points: list[tuple[int, int]] = []
    idx = 1
    for _ in range(n):
        x = int(data[idx])
        y = int(data[idx + 1])
        idx += 2
        points.append((x, y))

    area = polygon_area(points)
    perimeter = polygon_perimeter(points)

    print(f"{area:.1f}")
    print(f"{perimeter:.3f}")


if __name__ == "__main__":
    main()
