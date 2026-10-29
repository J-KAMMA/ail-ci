# task: Demonstrate method resolution order by defining a diamond inheritance pattern of four classes and printing the MRO names.
from typing import Type


class Base:
    """Root of the diamond."""

    def describe(self) -> str:
        return "Base.describe"


class Left(Base):
    """Left branch of the diamond."""

    def describe(self) -> str:
        return "Left.describe -> " + super().describe()


class Right(Base):
    """Right branch of the diamond."""

    def describe(self) -> str:
        return "Right.describe -> " + super().describe()


class Diamond(Left, Right):
    """Bottom of the diamond, inheriting from both branches."""

    def describe(self) -> str:
        return "Diamond.describe -> " + super().describe()


def print_mro(cls: Type[object]) -> None:
    """Print the method resolution order of a class, one name per line."""
    print(f"MRO of {cls.__name__}:")
    for index, klass in enumerate(cls.__mro__):
        print(f"  {index}: {klass.__name__}")
    print()


def main() -> None:
    print_mro(Diamond)
    print_mro(Left)
    print_mro(Right)

    names = [klass.__name__ for klass in Diamond.__mro__]
    print("Diamond MRO names:", " -> ".join(names))
    print()

    print("Call chain via super():")
    print(Diamond().describe())


if __name__ == "__main__":
    main()
