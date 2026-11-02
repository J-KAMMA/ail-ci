from typing import NamedTuple


class Point(NamedTuple):
    x: int
    y: int


class Task(NamedTuple):
    name: str
    priority: int = 3


def distance_sq(a: Point, b: Point) -> int:
    dx = a.x - b.x
    dy = a.y - b.y
    return dx * dx + dy * dy


def main() -> None:
    p = Point(1, 2)
    q = Point(4, 6)
    print(p)
    print(p.x, p.y)
    print(distance_sq(p, q))
    print(p[0], p[1])
    a, b = p
    print(a + b)
    print(p._asdict())
    print(p._replace(x=10))
    print(Point._fields)
    t = Task("write")
    u = Task("test", 1)
    print(t)
    print(u.name, u.priority)


main()
