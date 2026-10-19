import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    idx = 0
    n = int(data[idx])
    idx += 1
    capacity = int(data[idx])
    idx += 1

    items: list[tuple[int, int]] = []
    for _ in range(n):
        weight = int(data[idx])
        value = int(data[idx + 1])
        idx += 2
        items.append((weight, value))

    best: list[int] = [0] * (capacity + 1)
    for w in range(1, capacity + 1):
        current = best[w - 1]
        for weight, value in items:
            if weight <= w:
                candidate = best[w - weight] + value
                if candidate > current:
                    current = candidate
        best[w] = current

    print(best[capacity])


if __name__ == "__main__":
    main()
