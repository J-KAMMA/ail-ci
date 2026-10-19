import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    h: int = int(data[0])
    w: int = int(data[1])
    # Gather all digit characters after the header; this handles both
    # contiguous rows ("12345") and space-separated digits ("1 2 3 4 5").
    digits: str = "".join(data[2:])
    grid: list[list[int]] = [
        [int(ch) for ch in digits[i * w:(i + 1) * w]] for i in range(h)
    ]

    best: int | None = None
    best_r: int = 0
    best_c: int = 0
    for r in range(h - 1):
        for c in range(w - 1):
            s: int = grid[r][c] + grid[r][c + 1] + grid[r + 1][c] + grid[r + 1][c + 1]
            if best is None or s > best:
                best = s
                best_r = r
                best_c = c

    if best is not None:
        print(best_r, best_c, best)


if __name__ == "__main__":
    main()
