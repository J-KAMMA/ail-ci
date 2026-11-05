from __future__ import annotations

DEPTH = 13


class Node:
    def __init__(self, item: int, left: Node | None, right: Node | None) -> None:
        self.item: int = item
        self.left: Node | None = left
        self.right: Node | None = right


def make(depth: int, item: int) -> Node | None:
    if depth <= 0:
        return None
    return Node(item, make(depth - 1, item + 1), make(depth - 1, item + 1))


def check(node: Node | None) -> int:
    if node is None:
        return 0
    return node.item + check(node.left) + check(node.right)


def main() -> int:
    total = 0
    for d in range(1, DEPTH + 1):
        tree = make(d, d)
        total += check(tree)
    print(total)
    return 0



main()
