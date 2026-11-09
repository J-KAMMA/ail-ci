# task: Define a base class Shape with an abstract area method, subclass Rectangle and Circle, and print the areas of a fixed list of instances.
import math
from abc import ABC, abstractmethod


class Shape(ABC):
    """Abstract base class for geometric shapes."""

    @abstractmethod
    def area(self) -> float:
        """Return the area of the shape."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class Rectangle(Shape):
    """A rectangle defined by its width and height."""

    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height

    def area(self) -> float:
        return self.width * self.height

    def __repr__(self) -> str:
        return f"Rectangle(width={self.width}, height={self.height})"


class Circle(Shape):
    """A circle defined by its radius."""

    def __init__(self, radius: float) -> None:
        self.radius = radius

    def area(self) -> float:
        return math.pi * self.radius ** 2

    def __repr__(self) -> str:
        return f"Circle(radius={self.radius})"


def main() -> None:
    shapes: list[Shape] = [
        Rectangle(3, 4),
        Rectangle(2.5, 10),
        Circle(1),
        Circle(2.5),
        Rectangle(0, 7),
    ]

    for shape in shapes:
        print(f"{shape!r} -> area = {shape.area():.4f}")


if __name__ == "__main__":
    main()
