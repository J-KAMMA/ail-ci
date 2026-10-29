# task: Build a 64-bit bitboard of knight attacks from square e4 and print it as an 8 by 8 grid of characters.
from typing import Final


KNIGHT_OFFSETS: Final[tuple[tuple[int, int], ...]] = (
    (1, 2),
    (2, 1),
    (2, -1),
    (1, -2),
    (-1, -2),
    (-2, -1),
    (-2, 1),
    (-1, 2),
)

BOARD_SIZE: Final[int] = 8
FILES: Final[str] = "abcdefgh"


def square_to_coords(name: str) -> tuple[int, int]:
    """Convert an algebraic square name like 'e4' to (file, rank) indices (0-based)."""
    file_char, rank_char = name[0].lower(), name[1]
    file_index = FILES.index(file_char)
    rank_index = int(rank_char) - 1
    return file_index, rank_index


def knight_attacks(file: int, rank: int) -> int:
    """Return a 64-bit bitboard of squares attacked by a knight on (file, rank).

    Bit index = rank * 8 + file, so a1 is bit 0 and h8 is bit 63.
    """
    bitboard = 0
    for d_file, d_rank in KNIGHT_OFFSETS:
        target_file = file + d_file
        target_rank = rank + d_rank
        if 0 <= target_file < BOARD_SIZE and 0 <= target_rank < BOARD_SIZE:
            bitboard |= 1 << (target_rank * BOARD_SIZE + target_file)
    return bitboard & 0xFFFFFFFFFFFFFFFF


def render_bitboard(bitboard: int) -> list[str]:
    """Render a bitboard as 8 lines of characters, rank 8 at the top."""
    lines: list[str] = []
    for rank in reversed(range(BOARD_SIZE)):
        cells: list[str] = []
        for file in range(BOARD_SIZE):
            index = rank * BOARD_SIZE + file
            cells.append("X" if (bitboard >> index) & 1 else ".")
        lines.append(f"{rank + 1} " + " ".join(cells))
    lines.append("  " + " ".join(FILES))
    return lines


def main() -> None:
    square = "e4"
    file, rank = square_to_coords(square)
    attacks = knight_attacks(file, rank)

    print(f"Knight attacks from {square}")
    print(f"Bitboard: 0x{attacks:016X}")
    print()
    for line in render_bitboard(attacks):
        print(line)


if __name__ == "__main__":
    main()
