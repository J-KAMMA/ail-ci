import sys


def subtree(node: int, parent: list[int], weight: list[int], depth: int) -> int:
    total = weight[node] * (depth + 1)
    i = 0
    while i < len(parent):
        if parent[i] == node:
            total += subtree(i, parent, weight, depth + 1)
        i += 1
    return total


def maxdepth(node: int, parent: list[int], depth: int) -> int:
    best = depth
    i = 0
    while i < len(parent):
        if parent[i] == node:
            d = maxdepth(i, parent, depth + 1)
            if d > best:
                best = d
        i += 1
    return best


def main() -> int:
    n = 500
    weight: list[int] = []
    parent: list[int] = []
    i = 0
    while i < n:
        weight.append(i % 7 + 1)
        if i == 0:
            parent.append(-1)
        else:
            parent.append((i - 1) // 3)
        i += 1
    print("nodes=%d sum=%d depth=%d" % (n, subtree(0, parent, weight, 0), maxdepth(0, parent, 0)))
    return 0


main()
