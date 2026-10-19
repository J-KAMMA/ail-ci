import sys


def main() -> None:
    data = sys.stdin.read().split()
    h = int(data[0])
    w = int(data[1])
    digits = "".join(data[2:])
    grid: list[list[int]] = [
        [int(digits[r * w + c]) for c in range(w)] for r in range(h)
    ]

    maxima: list[tuple[int, int]] = []
    for r in range(h):
        for c in range(w):
            value = grid[r][c]
            is_max = True
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w and grid[nr][nc] >= value:
                    is_max = False
                    break
            if is_max:
                maxima.append((r, c))

    for r, c in maxima:
        print(f"{r} {c}")
    print(len(maxima))


if __name__ == "__main__":
    main()
