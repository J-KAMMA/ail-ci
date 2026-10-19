import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    n = int(data[0])
    points: list[tuple[int, int]] = []
    idx = 1
    for _ in range(n):
        x = int(data[idx])
        y = int(data[idx + 1])
        idx += 2
        points.append((x, y))

    points.sort()

    for x, y in points:
        print(f"{x} {y}")

    if points:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        print(f"bbox {min(xs)} {min(ys)} {max(xs)} {max(ys)}")
    else:
        print("bbox empty")

    print(f"distinct {len(set(points))}")


if __name__ == "__main__":
    main()
