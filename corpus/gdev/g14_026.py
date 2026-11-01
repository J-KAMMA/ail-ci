# task: Implement a dataclass Stack with push and pop methods and demonstrate its behavior with a sequence of operations.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


class EmptyStackError(IndexError):
    """Raised when popping or peeking an empty stack."""


@dataclass
class Stack(Generic[T]):
    """A simple LIFO stack backed by a Python list."""

    _items: list[T] = field(default_factory=list)

    def push(self, item: T) -> None:
        """Push an item onto the top of the stack."""
        self._items.append(item)

    def pop(self) -> T:
        """Remove and return the top item. Raises EmptyStackError if empty."""
        if not self._items:
            raise EmptyStackError("pop from empty stack")
        return self._items.pop()

    def peek(self) -> T:
        """Return the top item without removing it. Raises EmptyStackError if empty."""
        if not self._items:
            raise EmptyStackError("peek at empty stack")
        return self._items[-1]

    def is_empty(self) -> bool:
        """Return True if the stack has no items."""
        return not self._items

    def __len__(self) -> int:
        return len(self._items)


def main() -> None:
    stack: Stack[int] = Stack()
    print(f"Initial: {stack}, empty={stack.is_empty()}, size={len(stack)}")

    for value in (10, 20, 30):
        stack.push(value)
        print(f"push({value}) -> size={len(stack)}, top={stack.peek()}")

    print(f"pop() -> {stack.pop()}")
    print(f"pop() -> {stack.pop()}")

    stack.push(40)
    print(f"push(40) -> size={len(stack)}, top={stack.peek()}")

    print(f"pop() -> {stack.pop()}")
    print(f"pop() -> {stack.pop()}")
    print(f"empty={stack.is_empty()}, size={len(stack)}")

    try:
        stack.pop()
    except EmptyStackError as exc:
        print(f"Caught expected error: {exc}")

    try:
        stack.peek()
    except EmptyStackError as exc:
        print(f"Caught expected error: {exc}")

    words: Stack[str] = Stack()
    for word in ["alpha", "beta", "gamma"]:
        words.push(word)
    reversed_words = [words.pop() for _ in range(len(words))]
    print(f"Reversed words: {reversed_words}")


if __name__ == "__main__":
    main()
