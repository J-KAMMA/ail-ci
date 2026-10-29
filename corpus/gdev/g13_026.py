# task: Build a Queue base class using a list and a PriorityQueue subclass that orders items by a key, printing dequeue order for fixed inserts.
from __future__ import annotations

import bisect
from typing import Callable, Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K")


class Queue(Generic[T]):
    """A simple FIFO queue backed by a Python list."""

    def __init__(self) -> None:
        self._items: list[T] = []

    def enqueue(self, item: T) -> None:
        """Add an item to the back of the queue."""
        self._items.append(item)

    def dequeue(self) -> T:
        """Remove and return the item at the front of the queue."""
        if self.is_empty():
            raise IndexError("dequeue from empty queue")
        return self._items.pop(0)

    def is_empty(self) -> bool:
        return not self._items

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._items!r})"


class PriorityQueue(Queue[T], Generic[T, K]):
    """
    A queue that always dequeues the item with the smallest key.

    Items with equal keys keep their insertion order (stable behaviour).
    Keys are kept in a parallel sorted list so that insertion position
    can be found with binary search.
    """

    def __init__(self, key: Callable[[T], K]) -> None:
        super().__init__()
        self._key: Callable[[T], K] = key
        self._keys: list[K] = []

    def enqueue(self, item: T) -> None:
        k = self._key(item)
        # bisect_right places new equal-key items after existing ones.
        index = bisect.bisect_right(self._keys, k)
        self._keys.insert(index, k)
        self._items.insert(index, item)

    def dequeue(self) -> T:
        if self.is_empty():
            raise IndexError("dequeue from empty priority queue")
        self._keys.pop(0)
        return self._items.pop(0)


def main() -> None:
    # Fixed inserts: (task name, priority where lower means more urgent)
    tasks: list[tuple[str, int]] = [
        ("write report", 3),
        ("fix bug", 1),
        ("reply to email", 2),
        ("deploy patch", 1),
        ("update docs", 5),
        ("review pull request", 2),
        ("backup database", 4),
    ]

    fifo: Queue[tuple[str, int]] = Queue()
    pq: PriorityQueue[tuple[str, int], int] = PriorityQueue(key=lambda t: t[1])

    for task in tasks:
        fifo.enqueue(task)
        pq.enqueue(task)

    print(f"Inserted {len(tasks)} tasks.")
    print()

    print("FIFO dequeue order:")
    while not fifo.is_empty():
        name, priority = fifo.dequeue()
        print(f"  {name} (priority {priority})")
    print()

    print("Priority dequeue order (lowest key first):")
    while not pq.is_empty():
        name, priority = pq.dequeue()
        print(f"  {name} (priority {priority})")


if __name__ == "__main__":
    main()
