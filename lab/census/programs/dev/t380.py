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

    points.sort(key=lambda p: (p[0] * p[0] + p[1] * p[1], p[0], p[1]))

    out_lines = [f"{x} {y}" for x, y in points[:10]]
    if out_lines:
        sys.stdout.write("\n".join(out_lines) + "\n")


if __name__ == "__main__":
    main()
