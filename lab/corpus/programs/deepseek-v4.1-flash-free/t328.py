import sys


class Fenwick:
    def __init__(self, values: list[int]) -> None:
        self.n = len(values)
        self.tree = [0] * (self.n + 1)
        for i, v in enumerate(values, start=1):
            self._add_raw(i, v)

    def _add_raw(self, i: int, delta: int) -> None:
        while i <= self.n:
            self.tree[i] += delta
            i += i & (-i)

    def add(self, index0: int, delta: int) -> None:
        self._add_raw(index0 + 1, delta)

    def prefix(self, i: int) -> int:
        total = 0
        while i > 0:
            total += self.tree[i]
            i -= i & (-i)
        return total

    def range_sum(self, left0: int, right0: int) -> int:
        return self.prefix(right0 + 1) - self.prefix(left0)


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return
    it = iter(data)
    n = int(next(it))
    q = int(next(it))
    values = [int(next(it)) for _ in range(n)]
    queries = [(int(next(it)), int(next(it))) for _ in range(q)]

    tree = Fenwick(values)

    out: list[str] = []
    for l, r in queries:
        out.append(str(tree.range_sum(l, r)))

    for i in range(0, n, 2):
        tree.add(i, 1)

    for l, r in queries:
        out.append(str(tree.range_sum(l, r)))

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
