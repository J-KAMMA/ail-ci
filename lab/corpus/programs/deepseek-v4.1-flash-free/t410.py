import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    width = 31
    center = width // 2
    cells = [0] * width
    cells[center] = 1

    for _ in range(n):
        print("".join("#" if c else "." for c in cells))
        nxt = [0] * width
        for i in range(width):
            left = cells[i - 1] if i - 1 >= 0 else 0
            mid = cells[i]
            right = cells[i + 1] if i + 1 < width else 0
            nxt[i] = left ^ (mid | right)
        cells = nxt


if __name__ == "__main__":
    main()
