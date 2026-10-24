# task: Write a script that determines the winner of a hardcoded 3x3 tic-tac-toe board and prints X, O, or Draw.
from typing import Optional

Board = list[list[str]]


def find_winner(board: Board) -> Optional[str]:
    """Return 'X' or 'O' if that player has three in a line, otherwise None."""
    lines: list[list[str]] = []

    # Rows and columns
    for i in range(3):
        lines.append([board[i][0], board[i][1], board[i][2]])
        lines.append([board[0][i], board[1][i], board[2][i]])

    # Diagonals
    lines.append([board[0][0], board[1][1], board[2][2]])
    lines.append([board[0][2], board[1][1], board[2][0]])

    for line in lines:
        if line[0] != " " and line[0] == line[1] == line[2]:
            return line[0]
    return None


def main() -> None:
    board: Board = [
        ["X", "O", "X"],
        ["O", "X", "O"],
        ["O", "X", "X"],
    ]

    winner = find_winner(board)
    if winner is None:
        print("Draw")
    else:
        print(winner)


if __name__ == "__main__":
    main()
