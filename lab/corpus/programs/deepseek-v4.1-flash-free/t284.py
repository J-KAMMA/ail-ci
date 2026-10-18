import sys


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
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
    it = iter(data)
    n = int(next(it))
    m = int(next(it))

    uf = UnionFind(n)
    for _ in range(m):
        a = int(next(it))
        b = int(next(it))
        uf.union(a, b)

    counts: dict[int, int] = {}
    for v in range(n):
        r = uf.find(v)
        counts[r] = counts.get(r, 0) + 1
    sizes = sorted(counts.values())

    root0 = uf.find(0)
    comp0 = sorted(v for v in range(n) if uf.find(v) == root0)

    out = []
    out.append(" ".join(map(str, sizes)))
    out.append(" ".join(map(str, comp0)))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
