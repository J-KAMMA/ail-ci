import sys


def count_inversions(a: list[int]) -> int:
    n = len(a)
    if n < 2:
        return 0

    ranks = {v: i + 1 for i, v in enumerate(sorted(set(a)))}
    tree = [0] * (len(ranks) + 1)

    def update(i: int) -> None:
        while i < len(tree):
            tree[i] += 1
            i += i & (-i)

    def query(i: int) -> int:
        s = 0
        while i > 0:
            s += tree[i]
            i -= i & (-i)
        return s

    inversions = 0
    seen = 0
    for value in a:
        r = ranks[value]
        inversions += seen - query(r)
        update(r)
        seen += 1
    return inversions


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return
    n = int(data[0])
    a = [int(x) for x in data[1:1 + n]]
    print(count_inversions(a))


if __name__ == "__main__":
    main()
