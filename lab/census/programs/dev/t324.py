import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print("0 0")
        return

    n = int(data[0])
    events: list[tuple[int, int]] = []
    idx = 1
    for _ in range(n):
        start = int(data[idx])
        end = int(data[idx + 1])
        idx += 2
        # Half-open intervals [start, end): ends (-1) sort before starts (+1) at equal times.
        events.append((start, 1))
        events.append((end, -1))

    events.sort()

    current = 0
    best = 0
    best_time = 0
    for time, delta in events:
        current += delta
        if delta == 1 and current > best:
            best = current
            best_time = time

    print(best, best_time)


if __name__ == "__main__":
    main()
