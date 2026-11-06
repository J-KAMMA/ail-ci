# task: Write a script that counts the number of distinct reachable tic-tac-toe positions by exhaustive play and prints the total.
from typing import Optional

Board = tuple[str, ...]

WIN_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
)


def winner(board: Board) -> Optional[str]:
    """Return 'X' or 'O' if that player has three in a row, else None."""
    for a, b, c in WIN_LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return None


def next_player(board: Board) -> str:
    """X moves first; players alternate, so the mover is determined by piece counts."""
    x_count = board.count("X")
    o_count = board.count("O")
    return "X" if x_count == o_count else "O"


def successors(board: Board) -> list[Board]:
    """All boards reachable by one legal move from a non-terminal position."""
    player = next_player(board)
    result: list[Board] = []
    for i, cell in enumerate(board):
        if cell == " ":
            new_board = board[:i] + (player,) + board[i + 1:]
            result.append(new_board)
    return result


def count_reachable_positions() -> int:
    """Breadth-first exhaustive play from the empty board.

    Games stop as soon as someone wins or the board is full, so those
    terminal positions are counted but not expanded further.
    """
    start: Board = (" ",) * 9
    seen: set[Board] = {start}
    frontier: list[Board] = [start]

    while frontier:
        next_frontier: list[Board] = []
        for board in frontier:
            if winner(board) is not None or " " not in board:
                continue
            for child in successors(board):
                if child not in seen:
                    seen.add(child)
                    next_frontier.append(child)
        frontier = next_frontier

    return len(seen)


def main() -> None:
    total = count_reachable_positions()
    print(f"Distinct reachable tic-tac-toe positions: {total}")


if __name__ == "__main__":
    main()
