# task: Simulate a 1D cellular automaton of Rule 30 on a 31-cell row for 15 generations and print each row as a line of # and spaces.
from typing import List

RULE: int = 30
WIDTH: int = 31
GENERATIONS: int = 15


def step(row: List[int]) -> List[int]:
    """Compute the next generation of Rule 30 with fixed (zero) boundaries."""
    n = len(row)
    new_row = [0] * n
    for i in range(n):
        left = row[i - 1] if i > 0 else 0
        center = row[i]
        right = row[i + 1] if i < n - 1 else 0
        pattern = (left << 2) | (center << 1) | right
        new_row[i] = (RULE >> pattern) & 1
    return new_row


def render(row: List[int]) -> str:
    """Render a row of cells as '#' for live cells and ' ' for dead cells."""
    return "".join("#" if cell else " " for cell in row)


def main() -> None:
    row: List[int] = [0] * WIDTH
    row[WIDTH // 2] = 1

    print(render(row))
    for _ in range(GENERATIONS):
        row = step(row)
        print(render(row))


if __name__ == "__main__":
    main()
