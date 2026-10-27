# task: Write a script that generates a fixed-seed 13-card hand, sorts it by suit and then rank, and prints the sorted result.
import random
from typing import NamedTuple


SUITS: tuple[str, ...] = ("Clubs", "Diamonds", "Hearts", "Spades")
RANKS: tuple[str, ...] = (
    "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"
)
SEED: int = 2024
HAND_SIZE: int = 13


class Card(NamedTuple):
    rank: str
    suit: str

    def __str__(self) -> str:
        return f"{self.rank} of {self.suit}"


def build_deck() -> list[Card]:
    return [Card(rank, suit) for suit in SUITS for rank in RANKS]


def deal_hand(deck: list[Card], size: int) -> list[Card]:
    return random.sample(deck, size)


def sort_key(card: Card) -> tuple[int, int]:
    return (SUITS.index(card.suit), RANKS.index(card.rank))


def main() -> None:
    random.seed(SEED)
    deck = build_deck()
    hand = deal_hand(deck, HAND_SIZE)
    sorted_hand = sorted(hand, key=sort_key)

    print(f"Fixed-seed hand (seed={SEED}, {HAND_SIZE} cards):")
    for index, card in enumerate(sorted_hand, start=1):
        print(f"{index:2d}. {card}")


if __name__ == "__main__":
    main()
