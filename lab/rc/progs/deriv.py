from __future__ import annotations

DEPTH = 15

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
        return leaf(seed % 9 + 1)
    if seed % 2 == 0:
        return Expr(ADD, 0, build(depth - 1, seed + 1), build(depth - 1, seed + 2))
    return Expr(MUL, 0, build(depth - 1, seed + 1), build(depth - 1, seed + 2))


def deriv(e: Expr) -> Expr:
    if e.op == LEAF:
        return leaf(0)
    if e.op == ADD:
        return Expr(ADD, 0, deriv(e.left), deriv(e.right))
    return Expr(ADD, 0, Expr(MUL, 0, deriv(e.left), e.right),
                Expr(MUL, 0, e.left, deriv(e.right)))


def size(e: Expr) -> int:
    if e.op == LEAF:
        return 1
    return 1 + size(e.left) + size(e.right)


def checksum(e: Expr) -> int:
    if e.op == LEAF:
        return e.value
    return (checksum(e.left) * 31 + checksum(e.right) * 17 + e.op) % 1000003


def main() -> int:
    e = build(DEPTH, 1)
    d = deriv(e)
    print(size(e))
    print(size(d))
    print(checksum(d))
    return 0


main()
