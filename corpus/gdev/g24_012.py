# task: Write a script that simulates Snakes and Ladders on a 100-square board with a fixed-seed die and prints the number of turns needed to finish.
import random
from typing import Final

BOARD_SIZE: Final[int] = 100
SEED: Final[int] = 2024

LADDERS: Final[dict[int, int]] = {
    1: 38,
    4: 14,
    9: 31,
    21: 42,
    28: 84,
    36: 44,
    51: 67,
    71: 91,
    80: 100,
}

SNAKES: Final[dict[int, int]] = {
    16: 6,
    47: 26,
    49: 11,
    56: 53,
    62: 19,
    64: 60,
    87: 24,
    93: 73,
    95: 75,
    98: 78,
}

JUMPS: Final[dict[int, int]] = {**LADDERS, **SNAKES}


def roll_die(rng: random.Random) -> int:
    """Roll a fair six-sided die."""
    return rng.randint(1, 6)


def apply_jump(square: int) -> int:
    """Return the square reached after applying any ladder or snake."""
    return JUMPS.get(square, square)


def play_game(rng: random.Random) -> int:
    """Play one game from square 0 until reaching square 100; return turns taken.

    A roll that would overshoot the final square is forfeited (the player stays put).
    """
    position: int = 0
    turns: int = 0
    while position != BOARD_SIZE:
        turns += 1
        roll = roll_die(rng)
        target = position + roll
        if target > BOARD_SIZE:
            continue
        position = apply_jump(target)
    return turns


def main() -> None:
    random.seed(SEED)
    rng = random.Random(SEED)
    turns = play_game(rng)
    print(f"Snakes and Ladders finished in {turns} turns.")


if __name__ == "__main__":
    main()
