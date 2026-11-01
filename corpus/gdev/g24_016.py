# task: Write a script that checks a hardcoded 6x7 Connect Four board for a four-in-a-row win and prints the coordinates of the winning line.
from typing import Final

BOARD: Final[tuple[str, ...]] = (
    ".......",
    ".......",
    "...X...",
    "..XO...",
    ".XOO...",
    "XOXXO..",
)

ROWS: Final[int] = 6
COLS: Final[int] = 7
DIRECTIONS: Final[tuple[tuple[int, int], ...]] = ((0, 1), (1, 0), (1, 1), (1, -1))


def find_winning_lines(board: tuple[str, ...]) -> list[tuple[str, tuple[tuple[int, int], ...]]]:
    """Return all four-in-a-row lines as (symbol, coordinates) pairs, sorted."""
    wins: set[tuple[str, tuple[tuple[int, int], ...]]] = set()
    for r in range(ROWS):
        for c in range(COLS):
            symbol = board[r][c]
            if symbol == ".":
                continue
            for dr, dc in DIRECTIONS:
                cells = [(r + i * dr, c + i * dc) for i in range(4)]
                if not all(0 <= rr < ROWS and 0 <= cc < COLS for rr, cc in cells):
                    continue
                if all(board[rr][cc] == symbol for rr, cc in cells):
                    wins.add((symbol, tuple(sorted(cells))))
    return sorted(wins, key=lambda item: (item[0], item[1]))


def main() -> None:
    wins = find_winning_lines(BOARD)
    if not wins:
        print("No four-in-a-row found.")
        return
    for symbol, cells in wins:
        coords = ", ".join(f"({r}, {c})" for r, c in cells)
        print(f"Player {symbol} wins with line: {coords}")


if __name__ == "__main__":
    main()
