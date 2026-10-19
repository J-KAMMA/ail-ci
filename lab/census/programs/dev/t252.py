import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    values = list(map(int, data[1:1 + n * n]))

    # Build the adjacency/reachability matrix: edge i -> j iff entry > 0.
    reach: list[list[bool]] = [
        [values[i * n + j] > 0 for j in range(n)] for i in range(n)
    ]

    # Floyd-Warshall transitive closure.
    for k in range(n):
        row_k = reach[k]
        for i in range(n):
            if reach[i][k]:
                row_i = reach[i]
                for j in range(n):
                    if row_k[j]:
                        row_i[j] = True

    lines = [" ".join("1" if reach[i][j] else "0" for j in range(n)) for i in range(n)]
    if lines:
        sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
