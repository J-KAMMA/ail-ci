import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print("none")
        return

    n = int(data[0])
    available = (len(data) - 1) // 2
    count = min(n, available)

    points: list[tuple[int, int]] = []
    for k in range(count):
        x = int(data[1 + 2 * k])
        y = int(data[2 + 2 * k])
        points.append((x, y))

    points.sort()

    if len(points) < 2:
        print("none")
        return

    best: int | None = None
    best_i = 0
    best_j = 1

    for i in range(len(points)):
        x1, y1 = points[i]
        for j in range(i + 1, len(points)):
            x2, y2 = points[j]
            dx = x2 - x1
            dy = y2 - y1
            d2 = dx * dx + dy * dy
            if best is None or d2 < best:
                best = d2
                best_i = i
                best_j = j

    assert best is not None
    px, py = points[best_i]
    qx, qy = points[best_j]
    print(f"{px} {py} {qx} {qy} {best}")


if __name__ == "__main__":
    main()
