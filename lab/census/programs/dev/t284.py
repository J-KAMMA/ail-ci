import sys


class DisjointSet:
    """Union-find with path compression and union by size."""

    def __init__(self, n: int) -> None:
        self.parent: list[int] = list(range(n))
        self.size: list[int] = [1] * n

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            nxt = self.parent[x]
            self.parent[x] = root
            x = nxt
        return root

    def union(self, a: int, b: int) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    m = int(data[1]) if len(data) > 1 else 0

    dsu = DisjointSet(n)
    idx = 2
    for _ in range(m):
        a = int(data[idx])
        b = int(data[idx + 1])
        idx += 2
        dsu.union(a, b)

    counts: dict[int, int] = {}
    for v in range(n):
        r = dsu.find(v)
        counts[r] = counts.get(r, 0) + 1

    sizes = sorted(counts.values())

    if n > 0:
        root0 = dsu.find(0)
        comp0 = sorted(v for v in range(n) if dsu.find(v) == root0)
    else:
        comp0 = []

    print(sizes)
    print(comp0)


if __name__ == "__main__":
    main()
