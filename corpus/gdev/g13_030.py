# task: Define a Node-based Linked structure with a base class and a DoublyLinkedNode subclass that adds a prev pointer, printing traversal results in both directions.
from __future__ import annotations

from typing import Generic, Optional, TypeVar, Iterator

T = TypeVar("T")


class Node(Generic[T]):
    """Base singly-linked node holding a value and a pointer to the next node."""

    def __init__(self, value: T, next_node: Optional[Node[T]] = None) -> None:
        self.value: T = value
        self.next: Optional[Node[T]] = next_node

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.value!r})"


class LinkedList(Generic[T]):
    """Singly-linked list built from Node objects."""

    def __init__(self) -> None:
        self.head: Optional[Node[T]] = None
        self.size: int = 0

    def append(self, value: T) -> Node[T]:
        new_node: Node[T] = Node(value)
        if self.head is None:
            self.head = new_node
        else:
            current: Node[T] = self.head
            while current.next is not None:
                current = current.next
            current.next = new_node
        self.size += 1
        return new_node

    def __iter__(self) -> Iterator[T]:
        current: Optional[Node[T]] = self.head
        while current is not None:
            yield current.value
            current = current.next

    def __len__(self) -> int:
        return self.size


class DoublyLinkedNode(Node[T]):
    """Node that also keeps a pointer to the previous node."""

    def __init__(
        self,
        value: T,
        next_node: Optional[Node[T]] = None,
        prev_node: Optional[DoublyLinkedNode[T]] = None,
    ) -> None:
        super().__init__(value, next_node)
        self.prev: Optional[DoublyLinkedNode[T]] = prev_node


class DoublyLinkedList(Generic[T]):
    """Doubly-linked list that supports traversal in both directions."""

    def __init__(self) -> None:
        self.head: Optional[DoublyLinkedNode[T]] = None
        self.tail: Optional[DoublyLinkedNode[T]] = None
        self.size: int = 0

    def append(self, value: T) -> DoublyLinkedNode[T]:
        new_node: DoublyLinkedNode[T] = DoublyLinkedNode(value)
        if self.tail is None:
            self.head = new_node
            self.tail = new_node
        else:
            self.tail.next = new_node
            new_node.prev = self.tail
            self.tail = new_node
        self.size += 1
        return new_node

    def prepend(self, value: T) -> DoublyLinkedNode[T]:
        new_node: DoublyLinkedNode[T] = DoublyLinkedNode(value)
        if self.head is None:
            self.head = new_node
            self.tail = new_node
        else:
            new_node.next = self.head
            self.head.prev = new_node
            self.head = new_node
        self.size += 1
        return new_node

    def forward(self) -> Iterator[T]:
        current: Optional[DoublyLinkedNode[T]] = self.head
        while current is not None:
            yield current.value
            current = current.next  # type: ignore[assignment]

    def backward(self) -> Iterator[T]:
        current: Optional[DoublyLinkedNode[T]] = self.tail
        while current is not None:
            yield current.value
            current = current.prev

    def __len__(self) -> int:
        return self.size


def main() -> None:
    # Singly-linked list demo
    singly: LinkedList[str] = LinkedList()
    for word in ["alpha", "beta", "gamma"]:
        singly.append(word)
    print("Singly linked list:", list(singly))
    print("Length:", len(singly))
    print()

    # Doubly-linked list demo
    doubly: DoublyLinkedList[int] = DoublyLinkedList()
    for number in range(1, 6):
        doubly.append(number * 10)
    doubly.prepend(5)
    doubly.prepend(0)

    print("Doubly linked list traversal:")
    print("  forward :", list(doubly.forward()))
    print("  backward:", list(doubly.backward()))
    print("  length  :", len(doubly))
    print()

    # Verify that prev/next pointers are consistent in both directions
    forward_values = list(doubly.forward())
    backward_values = list(doubly.backward())
    consistent = forward_values == list(reversed(backward_values))
    print("Forward and backward traversals agree:", consistent)

    # Inspect individual nodes
    print()
    print("Node walk with neighbours:")
    node: Optional[DoublyLinkedNode[int]] = doubly.head
    while node is not None:
        prev_val = node.prev.value if node.prev is not None else None
        next_val = node.next.value if node.next is not None else None  # type: ignore[union-attr]
        print(f"  {node!r:<22} prev={prev_val!s:<5} next={next_val!s}")
        node = node.next  # type: ignore[assignment]


if __name__ == "__main__":
    main()
