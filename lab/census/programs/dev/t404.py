import sys


def main() -> None:
    data = sys.stdin.read().split()
    remaining: list[int] = [int(token) for token in data]

    current: int = 1
    total_distance: int = 0
    order: list[int] = []

    while remaining:
        # Pick the nearest remaining request; ties go to the earliest in input order.
        idx = min(
            range(len(remaining)),
            key=lambda i: (abs(remaining[i] - current), i),
        )
        floor = remaining.pop(idx)
        total_distance += abs(floor - current)
        current = floor
        order.append(floor)

    print(" ".join(str(f) for f in order))
    print(total_distance)


if __name__ == "__main__":
    main()
