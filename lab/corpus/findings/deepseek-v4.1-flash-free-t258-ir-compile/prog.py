import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print("none")
        return

    n = int(data[0])
    coords = data[1:]
    points = []
    for i in range(n):
        x = int(coords[2 * i])
        y = int(coords[2 * i + 1])
        points.append((x, y))

    if len(points) < 2:
        print("none")
        return

    points.sort()

    best_p1 = points[0]
    best_p2 = points[1]
    best_d2 = None

    for i in range(len(points)):
        x1, y1 = points[i]
        for j in range(i + 1, len(points)):
            x2, y2 = points[j]
            dx = x1 - x2
            dy = y1 - y2
            d2 = dx * dx + dy * dy
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_p1 = points[i]
                best_p2 = points[j]

    print(f"{best_p1[0]} {best_p1[1]} {best_p2[0]} {best_p2[1]} {best_d2}")


if __name__ == "__main__":
    main()
