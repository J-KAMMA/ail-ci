import sys


def main() -> None:
    data = sys.stdin.read().split()
    it = iter(data)
    n = int(next(it))
    m = int(next(it))

    adj: list[list[int]] = [[] for _ in range(n)]
    for _ in range(m):
        a = int(next(it))
        b = int(next(it))
        adj[a].append(b)
        adj[b].append(a)

    for i in range(n):
        adj[i].sort()

    out: list[str] = []

    for i in range(n):
        out.append(" ".join(map(str, adj[i])))

    for i in range(n):
        row = ["0"] * n
        for j in adj[i]:
            row[j] = "1"
        out.append(" ".join(row))

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
