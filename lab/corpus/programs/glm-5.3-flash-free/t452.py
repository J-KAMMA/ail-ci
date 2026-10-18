from __future__ import annotations

from collections.abc import Iterator


class Node:
    __slots__ = ("value", "next")

    def __init__(self, value: int, next: Node | None = None) -> None:
        self.value = value
        self.next = next


class LinkedList:
    def __init__(self) -> None:
        self.head: Node | None = None
        self.tail: Node | None = None

    def append(self, value: int) -> None:
        node = Node(value)
        if self.tail is None:
            self.head = node
            self.tail = node
        else:
            self.tail.next = node
            self.tail = node

    def reverse(self) -> None:
        prev: Node | None = None
        current = self.head
        self.tail = self.head
        while current is not None:
            nxt = current.next
            current.next = prev
            prev = current
            current = nxt
        self.head = prev

    def merge_sorted(self, other: LinkedList) -> LinkedList:
        result = LinkedList()
        a, b = self.head, other.head
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

    def to_sorted_list(self) -> list[int]:
        return sorted(self.values())

    def values(self) -> Iterator[int]:
        current = self.head
        while current is not None:
            yield current.value
            current = current.next

    def build_from_sorted(self, values: list[int]) -> None:
        for v in values:
            self.append(v)


def main() -> None:
    import sys

    data = sys.stdin.read().split()
    n = int(data[0])
    nums = [int(x) for x in data[1 : 1 + n]]

    mid = n // 2
    first = LinkedList()
    second = LinkedList()

    first_half = sorted(nums[:mid])
    second_half = sorted(nums[mid:])

    first.build_from_sorted(first_half)
    second.build_from_sorted(second_half)

    merged = first.merge_sorted(second)
    print(" ".join(str(v) for v in merged.values()))


if __name__ == "__main__":
    main()
