from __future__ import annotations

import sys
from typing import Iterable, Iterator, Optional


class Node:
    __slots__ = ("value", "next")

    def __init__(self, value: int, next: Optional["Node"] = None) -> None:
        self.value = value
        self.next = next


class LinkedList:
    def __init__(self) -> None:
        self.head: Optional[Node] = None
        self.tail: Optional[Node] = None
        self._size = 0

    def append(self, value: int) -> None:
        node = Node(value)
        if self.head is None:
            self.head = node
            self.tail = node
        else:
            assert self.tail is not None
            self.tail.next = node
            self.tail = node
        self._size += 1

    def extend(self, values: Iterable[int]) -> None:
        for value in values:
            self.append(value)

    def reverse(self) -> None:
        prev: Optional[Node] = None
        cur = self.head
        self.tail = self.head
        while cur is not None:
            nxt = cur.next
            cur.next = prev
            prev = cur
            cur = nxt
        self.head = prev

    def __iter__(self) -> Iterator[int]:
        cur = self.head
        while cur is not None:
            yield cur.value
            cur = cur.next

    def __len__(self) -> int:
        return self._size

    @staticmethod
    def merge(a: "LinkedList", b: "LinkedList") -> "LinkedList":
        result = LinkedList()
        pa, pb = a.head, b.head
        while pa is not None and pb is not None:
            if pa.value <= pb.value:
                result.append(pa.value)
                pa = pa.next
            else:
                result.append(pb.value)
                pb = pb.next
        while pa is not None:
            result.append(pa.value)
            pa = pa.next
        while pb is not None:
            result.append(pb.value)
            pb = pb.next
        return result


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    nums = [int(x) for x in data[1 : 1 + n]]

    mid = n // 2
    first = LinkedList()
    first.extend(sorted(nums[:mid]))
    second = LinkedList()
    second.extend(sorted(nums[mid:]))

    merged = LinkedList.merge(first, second)
    sys.stdout.write(" ".join(str(value) for value in merged) + "\n")


if __name__ == "__main__":
    main()
