import sys


def card_value(rank: str) -> int:
    if rank == "A":
        return 1
    if rank in "TJQK":
        return 10
    return int(rank)


def hand_total(cards: list[str]) -> int:
    total = 0
    aces = 0
    for card in cards:
        rank = card[0]
        if rank == "A":
            aces += 1
        total += card_value(rank)
    if aces > 0 and total + 10 <= 21:
        total += 10
    return total


def main() -> None:
    cards = sys.stdin.read().split()
    print(hand_total(cards))


if __name__ == "__main__":
    main()
