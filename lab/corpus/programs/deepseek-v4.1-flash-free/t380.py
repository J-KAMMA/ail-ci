import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    index = 0
    n = int(data[index])
    index += 1
    points: list[tuple[int, int]] = []
    for _ in range(n):
        x = int(data[index])
        y = int(data[index + 1])
        index += 2
        points.append((x, y))

    points.sort(key=lambda p: (p[0] * p[0] + p[1] * p[1], p[0], p[1]))

    out = "\n".join(f"{x} {y}" for x, y in points[:10])
    sys.stdout.write(out)


if __name__ == "__main__":
    main()
