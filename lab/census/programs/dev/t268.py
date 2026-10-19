import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    m = int(data[1]) if len(data) > 1 else 0

    degree: list[int] = [0] * n
    idx = 2
    for _ in range(m):
        if idx + 1 >= len(data):
            break
        a = int(data[idx])
        b = int(data[idx + 1])
        idx += 2
        degree[a] += 1
        degree[b] += 1

    print(" ".join(str(d) for d in degree))

    if n == 0:
        print()
        return

    max_deg = max(degree)
    max_nodes = [i for i, d in enumerate(degree) if d == max_deg]
    print(" ".join(str(v) for v in max_nodes))


if __name__ == "__main__":
    main()
