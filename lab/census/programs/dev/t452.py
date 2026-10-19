from __future__ import annotations

import sys
from typing import Iterable, Iterator, Optional


class Node:
    """A single node of a singly linked list."""

    __slots__ = ("value", "next")

    def __init__(self, value: int, next_node: Optional[Node] = None) -> None:
        self.value = value
        self.next = next_node


class LinkedList:
    """A simple singly linked list supporting append, reverse and sorted merge."""

    def __init__(self, values: Iterable[int] = ()) -> None:
        self.head: Optional[Node] = None
        self._tail: Optional[Node] = None
        for value in values:
            self.append(value)

    def append(self, value: int) -> None:
        node = Node(value)
        if self._tail is None:
            self.head = node
        else:
            self._tail.next = node
        self._tail = node

    def reverse(self) -> None:
        prev: Optional[Node] = None
        current = self.head
        self._tail = self.head
        while current is not None:
            following = current.next
            current.next = prev
            prev = current
            current = following
        self.head = prev

    def __iter__(self) -> Iterator[int]:
        current = self.head
        while current is not None:
            yield current.value
            current = current.next

    @staticmethod
    def merge_sorted(first: LinkedList, second: LinkedList) -> LinkedList:
        """Merge two sorted linked lists into a new sorted linked list."""
        result = LinkedList()
        a = first.head
        b = second.head
        while a is not None and b is not None:
            if a.value <= b.value:
                result.append(a.value)
                a = a.next
            else:
                result.append(b.value)
                b = b.next
        while a is not None:
            result.append(a.value)
            a = a.next
        while b is not None:
            result.append(b.value)
            b = b.next
        return result


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print()
        return

    n = int(data[0])
    numbers = [int(token) for token in data[1:1 + n]]

    mid = len(numbers) // 2
    first_half = sorted(numbers[:mid])
    second_half = sorted(numbers[mid:])

    first_list = LinkedList(first_half)
    second_list = LinkedList(second_half)

    merged = LinkedList.merge_sorted(first_list, second_list)
    print(" ".join(str(value) for value in merged))


if __name__ == "__main__":
    main()
