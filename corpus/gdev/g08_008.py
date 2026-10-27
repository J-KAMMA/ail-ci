# task: Use backtracking to find one knight's tour on a 5x5 board starting from a corner and print the move sequence as a grid of step numbers.
from typing import Final

SIZE: Final[int] = 5
MOVES: Final[list[tuple[int, int]]] = [
    (1, 2), (2, 1), (2, -1), (1, -2),
    (-1, -2), (-2, -1), (-2, 1), (-1, 2),
]


def in_bounds(row: int, col: int) -> bool:
    return 0 <= row < SIZE and 0 <= col < SIZE


def backtrack(board: list[list[int]], row: int, col: int, step: int) -> bool:
    """Extend the tour from (row, col), where `step` squares have been visited."""
    if step == SIZE * SIZE:
        return True
    for d_row, d_col in MOVES:
        next_row = row + d_row
        next_col = col + d_col
        if in_bounds(next_row, next_col) and board[next_row][next_col] == 0:
            board[next_row][next_col] = step + 1
            if backtrack(board, next_row, next_col, step + 1):
                return True
            board[next_row][next_col] = 0
    return False


def find_tour(start_row: int, start_col: int) -> list[list[int]] | None:
    board: list[list[int]] = [[0] * SIZE for _ in range(SIZE)]
    board[start_row][start_col] = 1
    if backtrack(board, start_row, start_col, 1):
        return board
    return None


def format_board(board: list[list[int]]) -> str:
    width = len(str(SIZE * SIZE))
    lines = [" ".join(str(cell).rjust(width) for cell in row) for row in board]
    return "\n".join(lines)


def main() -> None:
    start_row, start_col = 0, 0
    print(f"Knight's tour on a {SIZE}x{SIZE} board, starting at corner "
          f"({start_row}, {start_col}) (step numbers, 1-based):")
    tour = find_tour(start_row, start_col)
    if tour is None:
        print("No tour found.")
    else:
        print(format_board(tour))


if __name__ == "__main__":
    main()
