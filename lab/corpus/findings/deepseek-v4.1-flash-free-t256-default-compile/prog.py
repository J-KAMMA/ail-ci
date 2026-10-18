import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    coords = data[1:]
    points = set()
    for i in range(n):
        x = int(coords[2 * i])
        y = int(coords[2 * i + 1])
        points.add((x, y))

    sorted_points = sorted(points)
    for x, y in sorted_points:
        print(x, y)

    xs = [p[0] for p in sorted_points]
    ys = [p[1] for p in sorted_points]
    print(min(xs), min(ys), max(xs), max(ys))
    print(len(sorted_points))


if __name__ == "__main__":
    main()
