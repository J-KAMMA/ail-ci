import sys
from typing import List


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    m = int(data[1]) if len(data) > 1 else 0

    adj: List[List[int]] = [[] for _ in range(n)]
    idx = 2
    for _ in range(m):
        a = int(data[idx])
        b = int(data[idx + 1])
        idx += 2
        adj[a].append(b)
        adj[b].append(a)

    for lst in adj:
        lst.sort()

    sys.setrecursionlimit(max(10000, 2 * n + 100))

    visited = [False] * n
    preorder: List[int] = []
    postorder: List[int] = []

    def dfs(u: int) -> None:
        visited[u] = True
        preorder.append(u)
        for v in adj[u]:
            if not visited[v]:
                dfs(v)
        postorder.append(u)

    if n > 0:
        dfs(0)

    print(" ".join(map(str, preorder)))
    print(" ".join(map(str, postorder)))


if __name__ == "__main__":
    main()
