import sys


def build_prefix(grid: list[list[int]], h: int, w: int) -> list[list[int]]:
    prefix = [[0] * (w + 1) for _ in range(h + 1)]
    for i in range(1, h + 1):
        row_sum = 0
        for j in range(1, w + 1):
            row_sum += grid[i - 1][j - 1]
            prefix[i][j] = prefix[i - 1][j] + row_sum
    return prefix


def rect_sum(prefix: list[list[int]], r1: int, c1: int, r2: int, c2: int) -> int:
    return prefix[r2][c2] - prefix[r1][c2] - prefix[r2][c1] + prefix[r1][c1]


def main() -> None:
    data = sys.stdin.read().split()
    h = int(data[0])
    w = int(data[1])
    lines = data[2:2 + h]
    grid = [[int(ch) for ch in line] for line in lines]

    prefix = build_prefix(grid, h, w)

    total = rect_sum(prefix, 0, 0, h, w)
    mid_r = h // 2
    mid_c = w // 2
    top_left = rect_sum(prefix, 0, 0, mid_r, mid_c)
    bottom_right = rect_sum(prefix, mid_r, mid_c, h, w)

    print(total)
    print(top_left)
    print(bottom_right)


if __name__ == "__main__":
    main()
