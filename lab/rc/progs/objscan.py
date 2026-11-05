from __future__ import annotations

COUNT = 500000


class Item:
    def __init__(self, key: int, value: int) -> None:
        self.key: int = key
        self.value: int = value


def build(n: int) -> list[Item]:
    items: list[Item] = []
    for i in range(n):
        items.append(Item(i, i % 1009))
    return items


def scan(items: list[Item]) -> int:
    acc = 0
    for item in items:
        if item.key % 3 == 0:
            acc += item.value
        else:
            acc -= item.value
    return acc


def keysum(items: list[Item]) -> int:
    acc = 0
    for item in items:
        acc = (acc * 7 + item.key) % 1000000007
    return acc


def main() -> int:
    items = build(COUNT)
    print(scan(items))
    print(keysum(items))
    return 0



main()
