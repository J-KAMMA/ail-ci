import sys


RULE = 110


def step(cells: list[int], rule: int = RULE) -> list[int]:
    """Advance the ring-shaped rule-110 automaton by one generation."""
    size = len(cells)
    nxt: list[int] = [0] * size
    for i in range(size):
        left = cells[(i - 1) % size]
        center = cells[i]
        right = cells[(i + 1) % size]
        pattern = (left << 2) | (center << 1) | right
        nxt[i] = (rule >> pattern) & 1
    return nxt


def render(cells: list[int]) -> str:
    """Convert a generation to a string of '0' and '1' characters."""
    return "".join("1" if c else "0" for c in cells)


def main() -> None:
    n = int(sys.stdin.readline().strip())
    width = 40
    cells: list[int] = [0] * width
    cells[width - 1] = 1

    lines: list[str] = [render(cells)]
    for _ in range(n):
        cells = step(cells)
        lines.append(render(cells))

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
