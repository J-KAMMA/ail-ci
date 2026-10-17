import sys


def read_grid(text: str) -> tuple[int, int, list[list[int]]]:
    lines = text.splitlines()
    h, w = map(int, lines[0].split())
    digits = [int(ch) for line in lines[1:] for ch in line if "0" <= ch <= "9"]
    if len(digits) < h * w:
        raise ValueError("grid has fewer digits than expected")
    grid = [digits[i * w:(i + 1) * w] for i in range(h)]
    return h, w, grid


def prefix_sums(grid: list[list[int]]) -> list[list[int]]:
    h = len(grid)
    w = len(grid[0])
    P = [[0] * (w + 1) for _ in range(h + 1)]
    for i in range(h):
        row = grid[i]
        prev, cur = P[i], P[i + 1]
        running = 0
        for j in range(w):
            running += row[j]
            cur[j + 1] = prev[j + 1] + running
    return P


def rect_sum(P: list[list[int]], r0: int, c0: int, r1: int, c1: int) -> int:
    return P[r1][c1] - P[r0][c1] - P[r1][c0] + P[r0][c0]


def main() -> None:
    h, w, grid = read_grid(sys.stdin.read())
    P = prefix_sums(grid)
    total = rect_sum(P, 0, 0, h, w)
    top_left = rect_sum(P, 0, 0, h // 2, w // 2)
    bottom_right = rect_sum(P, h - h // 2, w - w // 2, h, w)
    print(total)
    print(top_left)
    print(bottom_right)


if __name__ == "__main__":
    main()
