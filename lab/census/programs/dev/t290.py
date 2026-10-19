import sys
from collections import deque

MOD = 1_000_000_007


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print(0)
        return

    n = int(data[0])
    m = int(data[1]) if len(data) > 1 else 0

    adj: list[list[int]] = [[] for _ in range(n)]
    indeg = [0] * n

    idx = 2
    for _ in range(m):
        if idx + 1 >= len(data):
            break
        a = int(data[idx])
        b = int(data[idx + 1])
        idx += 2
        adj[a].append(b)
        indeg[b] += 1

    # Kahn's algorithm for a topological order
    remaining = indeg[:]
    queue: deque[int] = deque(v for v in range(n) if remaining[v] == 0)
    order: list[int] = []
    while queue:
        v = queue.popleft()
        order.append(v)
        for w in adj[v]:
            remaining[w] -= 1
            if remaining[w] == 0:
                queue.append(w)

    # f[v] = number of paths from v to any sink (a sink contributes a trivial path)
    f = [0] * n
    for v in reversed(order):
        if not adj[v]:
            f[v] = 1
        else:
            total = 0
            for w in adj[v]:
                total += f[w]
            f[v] = total % MOD

    answer = 0
    for v in range(n):
        if indeg[v] == 0:
            answer += f[v]
    print(answer % MOD)


if __name__ == "__main__":
    main()
