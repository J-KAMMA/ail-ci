# task: Define an Enum for chess piece types with associated point values stored as enum values and print the total value of a fixed set of pieces.
from collections import Counter
from enum import Enum


class PieceType(Enum):
    # Each value is a (points, symbol) tuple so that pieces with equal
    # point values (knight and bishop) do not become aliases of each other.
    PAWN = (1, "P")
    KNIGHT = (3, "N")
    BISHOP = (3, "B")
    ROOK = (5, "R")
    QUEEN = (9, "Q")
    KING = (0, "K")

    @property
    def points(self) -> int:
        point_value: int = self.value[0]
        return point_value

    @property
    def symbol(self) -> str:
        return str(self.value[1])


def total_value(pieces: list[PieceType]) -> int:
    return sum(piece.points for piece in pieces)


def main() -> None:
    # A fixed army: 8 pawns, 2 knights, 2 bishops, 2 rooks, 1 queen, 1 king.
    pieces: list[PieceType] = (
        [PieceType.PAWN] * 8
        + [PieceType.KNIGHT] * 2
        + [PieceType.BISHOP] * 2
        + [PieceType.ROOK] * 2
        + [PieceType.QUEEN] * 1
        + [PieceType.KING] * 1
    )

    counts: Counter[PieceType] = Counter(pieces)

    print("Piece counts and values:")
    for piece_type in PieceType:
        count = counts[piece_type]
        subtotal = count * piece_type.points
        print(
            f"  {piece_type.name:<7} ({piece_type.symbol}) "
            f"x{count:<2} @ {piece_type.points} = {subtotal}"
        )

    print(f"Total pieces: {len(pieces)}")
    print(f"Total value: {total_value(pieces)}")


if __name__ == "__main__":
    main()
