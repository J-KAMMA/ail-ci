# task: Use isinstance and issubclass checks across a fixed hierarchy of Base, Mid, and Derived classes and print the boolean results.
from typing import Any


class Base:
    """Root of the fixed hierarchy."""


class Mid(Base):
    """Intermediate class derived from Base."""


class Derived(Mid):
    """Leaf class derived from Mid (and therefore Base)."""


class Unrelated:
    """A class outside the hierarchy."""


def check_isinstance(obj: Any, classes: tuple[type, ...]) -> list[bool]:
    """Return isinstance results of obj against each class in classes."""
    return [isinstance(obj, cls) for cls in classes]


def check_issubclass(sub: type, sups: tuple[type, ...]) -> list[bool]:
    """Return issubclass results of sub against each class in sups."""
    return [issubclass(sub, sup) for sup in sups]


def main() -> None:
    classes: tuple[type, ...] = (Base, Mid, Derived, Unrelated)
    names = [cls.__name__ for cls in classes]

    instances: list[tuple[str, Any]] = [
        ("Base()", Base()),
        ("Mid()", Mid()),
        ("Derived()", Derived()),
        ("Unrelated()", Unrelated()),
    ]

    print("isinstance checks:")
    print("object".ljust(14) + " ".join(n.ljust(10) for n in names))
    for label, obj in instances:
        results = check_isinstance(obj, classes)
        row = " ".join(str(r).ljust(10) for r in results)
        print(label.ljust(14) + row)

    print()
    print("issubclass checks:")
    print("class".ljust(14) + " ".join(n.ljust(10) for n in names))
    for sub in classes:
        results = check_issubclass(sub, classes)
        row = " ".join(str(r).ljust(10) for r in results)
        print(sub.__name__.ljust(14) + row)

    print()
    print("Spot checks:")
    print(f"issubclass(Derived, Base) = {issubclass(Derived, Base)}")
    print(f"issubclass(Base, Derived) = {issubclass(Base, Derived)}")
    print(f"isinstance(Derived(), Mid) = {isinstance(Derived(), Mid)}")
    print(f"isinstance(Mid(), Derived) = {isinstance(Mid(), Derived)}")
    print(f"issubclass(Unrelated, Base) = {issubclass(Unrelated, Base)}")
    print(f"isinstance(True, int) = {isinstance(True, int)}")
    print(f"issubclass(bool, int) = {issubclass(bool, int)}")


if __name__ == "__main__":
    main()
