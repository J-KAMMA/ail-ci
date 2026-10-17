import sys

WIDTH = 31
CENTER = WIDTH // 2
RULE = 30


def evolve(row: list[int]) -> list[int]:
    nxt: list[int] = []
    for i in range(WIDTH):
        left = row[i - 1] if i > 0 else 0
        centre = row[i]
        right = row[i + 1] if i + 1 < WIDTH else 0
        pattern = (left << 2) | (centre << 1) | right
        nxt.append((RULE >> pattern) & 1)
    return nxt


def render(row: list[int]) -> str:
    return "".join("#" if cell else "." for cell in row)


def main() -> None:
    n = int(sys.stdin.read().strip())
    row = [0] * WIDTH
    row[CENTER] = 1
    lines = [render(row)]
    for _ in range(n):
        row = evolve(row)
        lines.append(render(row))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
