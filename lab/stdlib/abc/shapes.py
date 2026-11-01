from abc import ABC, abstractmethod


class Shape(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def area(self) -> int:
        ...

    @abstractmethod
    def perimeter(self) -> int:
        ...

    def describe(self) -> str:
        return "%s area=%d perimeter=%d" % (self.name, self.area(), self.perimeter())


class Rectangle(Shape):
    def __init__(self, width: int, height: int) -> None:
        Shape.__init__(self, "rectangle")
        self.width = width
        self.height = height

    def area(self) -> int:
        return self.width * self.height

    def perimeter(self) -> int:
        return 2 * (self.width + self.height)


class Square(Shape):
    def __init__(self, side: int) -> None:
        Shape.__init__(self, "square")
        self.side = side

    def area(self) -> int:
        return self.side * self.side

    def perimeter(self) -> int:
        return 4 * self.side


shapes = [Rectangle(3, 4), Square(5), Rectangle(10, 2)]
total = 0
for shape in shapes:
    print(shape.describe())
    total = total + shape.area()
print("total", total)
