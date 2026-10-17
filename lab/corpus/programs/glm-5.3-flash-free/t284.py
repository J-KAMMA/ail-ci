import sys


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

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
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return
    n, m = int(data[0]), int(data[1])

    uf = UnionFind(n)
    idx = 2
    for _ in range(m):
        a, b = int(data[idx]), int(data[idx + 1])
        idx += 2
        uf.union(a, b)

    components: dict[int, list[int]] = {}
    for v in range(n):
        components.setdefault(uf.find(v), []).append(v)

    sizes = sorted((len(members) for members in components.values()))

    print(" ".join(map(str, sizes)))
    if n > 0:
        zero_root = uf.find(0)
        print(" ".join(map(str, sorted(components[zero_root]))))


if __name__ == "__main__":
    main()
