# task: Write a Comparable-style base class implementing __lt__ via an abstract key method, subclass it for Version objects, and print the sorted fixed list.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Comparable(ABC):
    """Base class providing ordering via an abstract key() method."""

    @abstractmethod
    def key(self) -> tuple[Any, ...]:
        """Return the tuple used for ordering comparisons."""

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Comparable):
            return NotImplemented
        return self.key() < other.key()


class Version(Comparable):
    """A dotted numeric version such as '1.2.3'."""

    def __init__(self, text: str) -> None:
        self.text: str = text
        self.parts: tuple[int, ...] = tuple(int(p) for p in text.split("."))

    def key(self) -> tuple[int, ...]:
        return self.parts

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"Version({self.text!r})"


FIXED_VERSIONS: list[str] = [
    "1.10.0",
    "1.2.3",
    "1.2",
    "0.9.12",
    "2.0.0",
    "1.2.10",
    "1.2.3.1",
    "0.10",
]


def main() -> None:
    versions: list[Version] = [Version(text) for text in FIXED_VERSIONS]
    for v in sorted(versions):
        print(v)


if __name__ == "__main__":
    main()
