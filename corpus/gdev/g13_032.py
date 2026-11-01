# task: Implement a Singleton-style base class using __new__ and a subclass demonstrating that instances are shared, printing identity comparisons.
from __future__ import annotations

from typing import Any


class Singleton:
    """Base class that ensures at most one instance exists per class."""

    _instances: dict[type, Any] = {}

    def __new__(cls, *args: Any, **kwargs: Any) -> Singleton:
        if cls not in Singleton._instances:
            instance = super().__new__(cls)
            Singleton._instances[cls] = instance
        return Singleton._instances[cls]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Guard so re-initialization does not reset state on repeated calls.
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.setup(*args, **kwargs)

    def setup(self, *args: Any, **kwargs: Any) -> None:
        """Hook for subclasses to perform one-time initialization."""
        pass


class Config(Singleton):
    """Example subclass holding shared configuration state."""

    def setup(self, name: str = "default", level: int = 0) -> None:
        self.name = name
        self.level = level
        self.values: dict[str, int] = {}

    def set_value(self, key: str, value: int) -> None:
        self.values[key] = value


def main() -> None:
    first = Config("app", 1)
    second = Config("other", 99)
    third = Config()

    print("first is second:", first is second)
    print("second is third:", second is third)
    print("first is third:", first is third)
    print("first == third:", first == third)

    print("name seen via third:", third.name)
    print("level seen via first:", first.level)

    first.set_value("retries", 3)
    print("value seen via second:", second.values["retries"])

    print("id(first) == id(second):", id(first) == id(second))
    print("id(first) == id(third):", id(first) == id(third))

    base_a = Singleton()
    base_b = Singleton()
    print("base singleton shared:", base_a is base_b)
    print("base differs from Config:", base_a is not first)


if __name__ == "__main__":
    main()
