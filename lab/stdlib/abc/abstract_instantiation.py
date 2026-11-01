from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def area(self) -> int:
        ...

    @abstractmethod
    def perimeter(self) -> int:
        ...


class Square(Shape):
    def __init__(self, side: int) -> None:
        self.side = side

    def area(self) -> int:
        return self.side * self.side


class Complete(Shape):
    def area(self) -> int:
        return 4

    def perimeter(self) -> int:
        return 8


for cls in (Shape, Square, Complete):
    try:
        obj = cls()
        print(cls.__name__, "built", obj.area(), obj.perimeter())
    except TypeError as exc:
        print(cls.__name__, type(exc).__name__, str(exc))
