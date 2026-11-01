# task: Use a match statement with class patterns on a small set of dataclass shapes to compute and print the area of each shape.
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Circle:
    radius: float


@dataclass(frozen=True)
class Rectangle:
    width: float
    height: float


@dataclass(frozen=True)
class Square:
    side: float


@dataclass(frozen=True)
class Triangle:
    base: float
    height: float


@dataclass(frozen=True)
class Ellipse:
    semi_major: float
    semi_minor: float


Shape = Circle | Rectangle | Square | Triangle | Ellipse


def area(shape: Shape) -> float:
    match shape:
        case Circle(radius=r):
            return math.pi * r * r
        case Rectangle(width=w, height=h):
            return w * h
        case Square(side=s):
            return s * s
        case Triangle(base=b, height=h):
            return 0.5 * b * h
        case Ellipse(semi_major=a, semi_minor=b):
            return math.pi * a * b
        case _:
            raise TypeError(f"Unknown shape: {shape!r}")


def describe(shape: Shape) -> str:
    match shape:
        case Circle(radius=r):
            return f"Circle(radius={r})"
        case Rectangle(width=w, height=h):
            return f"Rectangle(width={w}, height={h})"
        case Square(side=s):
            return f"Square(side={s})"
        case Triangle(base=b, height=h):
            return f"Triangle(base={b}, height={h})"
        case Ellipse(semi_major=a, semi_minor=b):
            return f"Ellipse(semi_major={a}, semi_minor={b})"
        case _:
            return repr(shape)


def main() -> None:
    shapes: list[Shape] = [
        Circle(radius=1.5),
        Rectangle(width=3.0, height=4.5),
        Square(side=2.0),
        Triangle(base=6.0, height=2.5),
        Ellipse(semi_major=3.0, semi_minor=1.25),
    ]

    total: float = 0.0
    for shape in shapes:
        a = area(shape)
        total += a
        print(f"{describe(shape)} -> area = {a:.4f}")

    print(f"Total area = {total:.4f}")


if __name__ == "__main__":
    main()
