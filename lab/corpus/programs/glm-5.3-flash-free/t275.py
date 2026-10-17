import sys


def main() -> None:
    data = sys.stdin.read().split()
    n, m = int(data[0]), int(data[1])

    adj: list[set[int]] = [set() for _ in range(n)]
    matrix: list[list[int]] = [[0] * n for _ in range(n)]

    idx = 2
    for _ in range(m):
        a, b = int(data[idx]), int(data[idx + 1])
        idx += 2
        adj[a].add(b)
        adj[b].add(a)
        matrix[a][b] = 1
        matrix[b][a] = 1

    lines: list[str] = []
    for v in range(n):
        lines.append(" ".join(str(u) for u in sorted(adj[v])))
    for row in matrix:
        lines.append("".join(str(x) for x in row))

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
