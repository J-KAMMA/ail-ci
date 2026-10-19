import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    n = int(data[0])
    m = int(data[1]) if len(data) > 1 else 0

    in_deg: list[int] = [0] * n
    out_deg: list[int] = [0] * n

    idx = 2
    for _ in range(m):
        if idx + 1 >= len(data):
            break
        a = int(data[idx])
        b = int(data[idx + 1])
        idx += 2
        out_deg[a] += 1
        in_deg[b] += 1

    for node in range(n):
        if in_deg[node] != out_deg[node]:
            print(node)


if __name__ == "__main__":
    main()
