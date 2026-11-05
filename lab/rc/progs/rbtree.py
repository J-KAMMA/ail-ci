from __future__ import annotations

COUNT = 100000


class Node:
    def __init__(self, key: int, red: bool, left: Node | None, right: Node | None) -> None:
        self.key: int = key
        self.red: bool = red
        self.left: Node | None = left
        self.right: Node | None = right


def is_red(n: Node | None) -> bool:
    if n is None:
        return False
    return n.red


def rotate_left(n: Node) -> Node:
    r = n.right
    if r is None:
        return n
    n.right = r.left
    r.left = n
    r.red = n.red
    n.red = True
    return r


def rotate_right(n: Node) -> Node:
    l = n.left
    if l is None:
        return n
    n.left = l.right
    l.right = n
    l.red = n.red
    n.red = True
    return l


def insert(n: Node | None, key: int) -> Node:
    if n is None:
        return Node(key, True, None, None)
    if key < n.key:
        n.left = insert(n.left, key)
    elif key > n.key:
        n.right = insert(n.right, key)
    else:
        return n
    if is_red(n.right) and not is_red(n.left):
        n = rotate_left(n)
    if is_red(n.left) and is_red(n.left.left):
        n = rotate_right(n)
    if is_red(n.left) and is_red(n.right):
        n.red = True
        n.left.red = False
        n.right.red = False
    return n


def walk(n: Node | None, acc: int) -> int:
    if n is None:
        return acc
    acc = walk(n.left, acc)
    acc = (acc * 31 + n.key) % 1000000007
    return walk(n.right, acc)


def main() -> int:
    root: Node | None = None
    for i in range(COUNT):
        root = insert(root, (i * 2654435761) % 262144)
    if root is not None:
        root.red = False
    print(walk(root, 0))
    return 0



main()
