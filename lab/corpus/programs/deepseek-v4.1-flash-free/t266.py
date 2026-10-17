import sys


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return
    it = iter(data)
    n = int(next(it))
    m = int(next(it))

    adj: list[list[int]] = [[] for _ in range(n)]
    for _ in range(m):
        a = int(next(it))
        b = int(next(it))
        adj[a].append(b)
        adj[b].append(a)

    for neighbours in adj:
        neighbours.sort()

    sys.setrecursionlimit(max(1000, 2 * n + 10))

    pre: list[int] = []
    post: list[int] = []
    seen = [False] * n

    def dfs(u: int) -> None:
        seen[u] = True
        pre.append(u)
        for v in adj[u]:
            if not seen[v]:
                dfs(v)
        post.append(u)

    dfs(0)

    sys.stdout.write(" ".join(map(str, pre)) + "\n")
    sys.stdout.write(" ".join(map(str, post)) + "\n")


if __name__ == "__main__":
    main()
