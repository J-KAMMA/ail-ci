from collections import namedtuple


Point = namedtuple("Point", ["x", "y", "label"], defaults=["?"])
Pair = namedtuple("Pair", "left right")


def main() -> int:
    a = Point(1, 2)
    b = Point(3, 4, "bee")
    c = Point(x=5, y=6, label="cee")
    print(a, b, c)
    print(a.x, a[0], a[-1], len(a))
    x, y, label = b
    print(x, y, label)
    print(a._fields, a._replace(y=20), a._asdict())
    print(Point._make([7, 8, "seven"]), Point._make([9, 10, "nine"]))
    points = [c, a, b]
    points.sort()
    for point in points:
        print(point.label, point.x + point.y)
    print(points[0] == Point(1, 2), points[0] == (1, 2))
    print(max(points), min(points, key=lambda p: p.y))
    print(Pair._fields, Pair(1, "one"))
    left, right = Pair("l", "r")
    print(left, right)
    print(a._replace(x=a.x + 10))
    print(Point._field_defaults)
    return 0


main()
