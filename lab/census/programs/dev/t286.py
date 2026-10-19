import sys


def find(parent: list[int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    m = int(data[1]) if len(data) > 1 else 0

    parent = list(range(n))
    size = [1] * n
    edges: list[tuple[int, int]] = []

    idx = 2
    for _ in range(m):
        if idx + 1 >= len(data):
            break
        a = int(data[idx])
        b = int(data[idx + 1])
        idx += 2
        edges.append((a, b))
        ra = find(parent, a)
        rb = find(parent, b)
        if ra != rb:
            if size[ra] < size[rb]:
                ra, rb = rb, ra
            parent[rb] = ra
            size[ra] += size[rb]

    edge_count = [0] * n
    for a, _ in edges:
        edge_count[find(parent, a)] += 1

    seen: dict[int, int] = {}
    for v in range(n):
        r = find(parent, v)
        if r in seen:
            continue
        k = len(seen) + 1
        seen[r] = k
        nodes = size[r]
        if edge_count[r] == nodes - 1:
            print(f"Component {k}: tree")
        else:
            print(f"Component {k}: has cycles")


if __name__ == "__main__":
    main()
