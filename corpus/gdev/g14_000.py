# task: Define a dataclass Point with x and y fields and print the dataclass repr of a few instances.
from dataclasses import dataclass


@dataclass
class Point:
    x: float
    y: float


def main() -> None:
    points: list[Point] = [
        Point(0, 0),
        Point(1.5, -2.0),
        Point(x=3, y=4),
    ]
    for p in points:
        print(repr(p))


if __name__ == "__main__":
    main()
