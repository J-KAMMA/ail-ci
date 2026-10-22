# task: Write a Animal base class with __init_subclass__ that registers each subclass in a registry, then print the sorted registry names.
from __future__ import annotations

from typing import ClassVar


class Animal:
    """Base class that registers every subclass in a class-level registry."""

    registry: ClassVar[dict[str, type["Animal"]]] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        Animal.registry[cls.__name__] = cls

    def speak(self) -> str:
        return f"{type(self).__name__} makes a sound"


class Dog(Animal):
    def speak(self) -> str:
        return "Woof"


class Cat(Animal):
    def speak(self) -> str:
        return "Meow"


class Cow(Animal):
    def speak(self) -> str:
        return "Moo"


class Sheep(Animal):
    pass


class Horse(Animal):
    def speak(self) -> str:
        return "Neigh"


def main() -> None:
    names: list[str] = sorted(Animal.registry)
    for name in names:
        print(name)


if __name__ == "__main__":
    main()
