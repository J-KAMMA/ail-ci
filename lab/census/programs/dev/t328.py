import sys


class Fenwick:
    """Fenwick tree (binary indexed tree) supporting point updates and prefix sums."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.tree: list[int] = [0] * (n + 1)

    def add(self, index: int, delta: int) -> None:
        """Add delta to the element at 0-based index."""
        i = index + 1
        while i <= self.n:
            self.tree[i] += delta
            i += i & (-i)

    def prefix(self, count: int) -> int:
        """Sum of the first `count` elements (indices 0..count-1)."""
        total = 0
        i = count
        while i > 0:
            total += self.tree[i]
            i -= i & (-i)
        return total

    def range_sum(self, left: int, right: int) -> int:
        """Inclusive range sum over 0-based indices [left, right]."""
        return self.prefix(right + 1) - self.prefix(left)


def main() -> None:
    data = sys.stdin.read().split()
    pos = 0

    n = int(data[pos])
    pos += 1
    q = int(data[pos])
    pos += 1

    values: list[int] = []
    for _ in range(n):
        values.append(int(data[pos]))
        pos += 1

    queries: list[tuple[int, int]] = []
    for _ in range(q):
        l = int(data[pos])
        r = int(data[pos + 1])
        pos += 2
        if l > r:
            l, r = r, l
        queries.append((l, r))

    fenwick = Fenwick(n)
    for i, v in enumerate(values):
        fenwick.add(i, v)

    out: list[str] = []
    for l, r in queries:
        out.append(str(fenwick.range_sum(l, r)))

    # Add 1 to every element at an even index.
    for i in range(0, n, 2):
        fenwick.add(i, 1)

    for l, r in queries:
        out.append(str(fenwick.range_sum(l, r)))

    if out:
        sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
