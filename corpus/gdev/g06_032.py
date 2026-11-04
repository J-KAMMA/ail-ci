# task: Write a script that computes the equivalence classes of a hardcoded set of pairs using union-find with set-based groups.
from __future__ import annotations

from typing import Hashable, Iterable, TypeVar

T = TypeVar("T", bound=Hashable)

PAIRS: list[tuple[str, str]] = [
    ("apple", "banana"),
    ("banana", "cherry"),
    ("delta", "echo"),
    ("foxtrot", "golf"),
    ("golf", "hotel"),
    ("hotel", "foxtrot"),
    ("india", "india"),
    ("juliet", "kilo"),
    ("echo", "lima"),
    ("kilo", "mike"),
    ("mike", "juliet"),
    ("zulu", "alpha"),
    ("cherry", "apple"),
    ("nova", "nova"),
    ("oscar", "papa"),
]


class UnionFind[T: Hashable]:
    """Union-find over hashable items, storing each group as a set."""

    def __init__(self, items: Iterable[T] = ()) -> None:
        self._parent: dict[T, T] = {}
        self._groups: dict[T, set[T]] = {}
        for item in items:
            self.add(item)

    def add(self, item: T) -> None:
        if item not in self._parent:
            self._parent[item] = item
            self._groups[item] = {item}

    def find(self, item: T) -> T:
        self.add(item)
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        # Path compression.
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, a: T, b: T) -> None:
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a == root_b:
            return
        # Merge the smaller group into the larger one.
        if len(self._groups[root_a]) < len(self._groups[root_b]):
            root_a, root_b = root_b, root_a
        self._parent[root_b] = root_a
        self._groups[root_a] |= self._groups.pop(root_b)

    def classes(self) -> list[list[T]]:
        """Return all equivalence classes, each sorted, ordered by smallest member."""
        result = [sorted(group) for group in self._groups.values()]
        result.sort(key=lambda cls: cls[0])
        return result


def compute_equivalence_classes(pairs: Iterable[tuple[T, T]]) -> list[list[T]]:
    uf: UnionFind[T] = UnionFind()
    for a, b in pairs:
        uf.add(a)
        uf.add(b)
        uf.union(a, b)
    return uf.classes()


def main() -> None:
    classes = compute_equivalence_classes(PAIRS)
    print(f"Number of pairs: {len(PAIRS)}")
    print(f"Number of equivalence classes: {len(classes)}")
    for index, cls in enumerate(classes, start=1):
        members = ", ".join(cls)
        print(f"Class {index} (size {len(cls)}): {members}")


if __name__ == "__main__":
    main()
