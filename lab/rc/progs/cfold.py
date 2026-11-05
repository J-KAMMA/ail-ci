from __future__ import annotations

DEPTH = 13

LEAF = 0
ADD = 1
MUL = 2


class Expr:
    def __init__(self, op: int, value: int, left: Expr | None, right: Expr | None) -> None:
        self.op: int = op
        self.value: int = value
        self.left: Expr | None = left
        self.right: Expr | None = right


def leaf(value: int) -> Expr:
    return Expr(LEAF, value, None, None)


def build(depth: int, seed: int) -> Expr:
    if depth <= 0:
        return leaf(seed % 7 + 1)
    if seed % 2 == 0:
        return Expr(ADD, 0, build(depth - 1, seed + 1), build(depth - 1, seed + 2))
    return Expr(MUL, 0, build(depth - 1, seed + 1), build(depth - 1, seed + 2))


def fold(e: Expr) -> Expr:
    if e.op == LEAF:
        return leaf(e.value)
    left = fold(e.left)
    right = fold(e.right)
    if left.op == LEAF and right.op == LEAF:
        if e.op == ADD:
            return leaf((left.value + right.value) % 1000000007)
        return leaf((left.value * right.value) % 1000000007)
    return Expr(e.op, 0, left, right)


def eval(e: Expr) -> int:
    if e.op == LEAF:
        return e.value
    a = eval(e.left)
    b = eval(e.right)
    if e.op == ADD:
        return (a + b) % 1000000007
    return (a * b) % 1000000007


def size(e: Expr) -> int:
    if e.op == LEAF:
        return 1
    return 1 + size(e.left) + size(e.right)


def checksum(e: Expr) -> int:
    if e.op == LEAF:
        return e.value
    return (checksum(e.left) * 31 + checksum(e.right) * 17 + e.op) % 1000003


def main() -> int:
    tree = build(DEPTH, 1)
    after_tree = fold(tree)
    print(size(tree))
    print(size(after_tree))
    print(eval(tree))
    print(eval(after_tree))
    print(checksum(after_tree))
    return 0


main()
