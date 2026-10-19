import sys


def step(cells: list[int]) -> list[int]:
    """Apply one generation of Rule 30 with fixed (zero) boundaries."""
    width = len(cells)
    new_cells = [0] * width
    for i in range(width):
        left = cells[i - 1] if i > 0 else 0
        center = cells[i]
        right = cells[i + 1] if i < width - 1 else 0
        # Rule 30: new = left XOR (center OR right)
        new_cells[i] = left ^ (center | right)
    return new_cells


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0]) if data else 0

    width = 31
    cells = [0] * width
    cells[width // 2] = 1

    lines: list[str] = []
    lines.append("".join("#" if c else "." for c in cells))
    for _ in range(n):
        cells = step(cells)
        lines.append("".join("#" if c else "." for c in cells))

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
