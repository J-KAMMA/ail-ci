# task: Write a script that ranks a fixed list of five-card poker hands from weakest to strongest and prints the ordered list.
from collections import Counter

RANK_VALUES: dict[str, int] = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
}

CATEGORY_NAMES: dict[int, str] = {
    0: "High card",
    1: "One pair",
    2: "Two pair",
    3: "Three of a kind",
    4: "Straight",
    5: "Flush",
    6: "Full house",
    7: "Four of a kind",
    8: "Straight flush",
}

HANDS: list[str] = [
    "2H 3D 5S 9C KD",
    "2C 3H 4S 8C AH",
    "2D 2H 3C 9S 9D",
    "5C 5D 5H 9S KC",
    "6H 7D 8C 9S 10D",
    "AS 2S 3S 4S 5S",
    "KS KH KD 4C 4H",
    "3S 7S 9S JS 2S",
    "QC QD QH QS 2D",
    "10H JH QH KH AH",
    "8C 8D 8H 3S 3C",
    "JD JC 4H 4S 9D",
    "AC AD 5H 6S 9C",
]


def parse_card(card: str) -> tuple[int, str]:
    """Split a card string such as '10H' into (rank value, suit)."""
    rank_text, suit = card[:-1], card[-1]
    return RANK_VALUES[rank_text], suit


def evaluate(hand: str) -> tuple[int, tuple[int, ...]]:
    """Return a comparable score: (category, tiebreak ranks), higher is stronger."""
    parsed = [parse_card(card) for card in hand.split()]
    ranks = [rank for rank, _ in parsed]
    suits = [suit for _, suit in parsed]

    counts = Counter(ranks)
    # Ranks ordered by multiplicity first, then by rank value, both descending.
    ordered = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    pattern = sorted(counts.values(), reverse=True)

    is_flush = len(set(suits)) == 1

    is_straight = False
    straight_high = 0
    if len(counts) == 5:
        unique = sorted(counts)
        if unique[-1] - unique[0] == 4:
            is_straight = True
            straight_high = unique[-1]
        elif unique == [2, 3, 4, 5, 14]:  # Ace-low straight (wheel)
            is_straight = True
            straight_high = 5

    if is_straight and is_flush:
        category = 8
    elif pattern == [4, 1]:
        category = 7
    elif pattern == [3, 2]:
        category = 6
    elif is_flush:
        category = 5
    elif is_straight:
        category = 4
    elif pattern == [3, 1, 1]:
        category = 3
    elif pattern == [2, 2, 1]:
        category = 2
    elif pattern == [2, 1, 1, 1]:
        category = 1
    else:
        category = 0

    if is_straight:
        tiebreak = (straight_high,)
    else:
        tiebreak = tuple(rank for rank, _ in ordered)

    return category, tiebreak


def main() -> None:
    scored = [(evaluate(hand), hand) for hand in HANDS]
    # Ascending sort: weakest first, strongest last. Stable for any exact ties.
    scored.sort(key=lambda item: item[0])

    print("Poker hands ranked from weakest to strongest:")
    for position, ((category, _), hand) in enumerate(scored, start=1):
        print(f"{position:2d}. {hand:<16} {CATEGORY_NAMES[category]}")


if __name__ == "__main__":
    main()
