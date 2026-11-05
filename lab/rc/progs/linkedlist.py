from __future__ import annotations

COUNT = 200000


class Node:
    def __init__(self, value: int, next: Node | None) -> None:
        self.value: int = value
        self.next: Node | None = next


def build(n: int) -> Node | None:
    head: Node | None = None
    for i in range(n):
        head = Node(i % 101, head)
    return head


def total(n: Node | None) -> int:
    acc = 0
    while n is not None:
        acc += n.value
        n = n.next
    return acc


def parity(n: Node | None) -> int:
    acc = 0
    while n is not None:
        acc = acc ^ n.value
        n = n.next
    return acc


def main() -> int:
    head = build(COUNT)
    print(total(head))
    print(parity(head))
    return 0



main()
