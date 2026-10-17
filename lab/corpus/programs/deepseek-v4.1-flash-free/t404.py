import sys


def main() -> None:
    line = sys.stdin.readline().split()
    requests = [int(x) for x in line]

    current = 1
    remaining = list(requests)
    order: list[int] = []
    distance = 0

    while remaining:
        nearest = min(remaining, key=lambda f: (abs(f - current), remaining.index(f)))
        distance += abs(nearest - current)
        current = nearest
        remaining.remove(nearest)
        order.append(nearest)

    print(" ".join(map(str, order)))
    print(distance)


if __name__ == "__main__":
    main()
