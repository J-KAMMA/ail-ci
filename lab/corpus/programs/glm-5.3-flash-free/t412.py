import sys

WIDTH = 40
RULE = 110
START_INDEX = 39


def initial_state() -> list[int]:
    cells = [0] * WIDTH
    cells[START_INDEX] = 1
    return cells


def step(cells: list[int]) -> list[int]:
    nxt: list[int] = []
    for i in range(WIDTH):
        left = cells[(i - 1) % WIDTH]
        center = cells[i]
        right = cells[(i + 1) % WIDTH]
        pattern = (left << 2) | (center << 1) | right
        nxt.append((RULE >> pattern) & 1)
    return nxt


def render(cells: list[int]) -> str:
    return "".join(str(c) for c in cells)


def main() -> None:
    n = int(sys.stdin.readline().strip())
    cells = initial_state()
    print(render(cells))
    for _ in range(n):
        cells = step(cells)
        print(render(cells))


if __name__ == "__main__":
    main()
