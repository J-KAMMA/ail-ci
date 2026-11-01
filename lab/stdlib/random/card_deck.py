import random


def make_deck() -> list[str]:
    suits = ["clubs", "diamonds", "hearts", "spades"]
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    deck = []
    for suit in suits:
        for rank in ranks:
            deck.append(rank + " of " + suit)
    return deck


def main() -> None:
    random.seed(99)
    deck = make_deck()
    random.shuffle(x=deck)
    hand = deck[:5]
    rest = deck[5:]
    print("hand", hand)
    print("rest", len(rest))
    print("top", random.choice(deck))
    random.shuffle(hand)
    print("sorted hand", sorted(hand))


main()
