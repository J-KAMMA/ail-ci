"""Graph search: build an adjacency list and run BFS/DFS over integer node ids."""


def build_graph(n: int, fanout: int) -> list[list[int]]:
    adj = []
    i = 0
    while i < n:
        row = []
        j = 0
        while j < fanout:
            row.append((i * 31 + j * 17 + 7) % n)
            j += 1
        adj.append(row)
        i += 1
    return adj


def bfs_reach(adj: list[list[int]], start: int) -> int:
    seen = [0] * len(adj)
    queue = [start]
    seen[start] = 1
    head = 0
    count = 0
    while head < len(queue):
        v = queue[head]
        head += 1
        count += 1
        row = adj[v]
        i = 0
        while i < len(row):
            w = row[i]
            if seen[w] == 0:
                seen[w] = 1
                queue.append(w)
            i += 1
    return count


def dfs_count(adj: list[list[int]], start: int) -> int:
    seen = [0] * len(adj)
    stack = [start]
    seen[start] = 1
    count = 0
    while len(stack) > 0:
        v = stack.pop()
        count += 1
        row = adj[v]
        i = 0
        while i < len(row):
            w = row[i]
            if seen[w] == 0:
                seen[w] = 1
                stack.append(w)
            i += 1
    return count


def degree_sum(adj: list[list[int]]) -> int:
    total = 0
    for row in adj:
        total += len(row)
    return total


def edges_above(adj: list[list[int]], lo: int) -> int:
    total = 0
    for row in adj:
        for w in row:
            if w >= lo:
                total += 1
    return total


def max_degree(adj: list[list[int]]) -> int:
    best = 0
    for row in adj:
        if len(row) > best:
            best = len(row)
    return best
