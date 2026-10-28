# task: Write a script that simulates one round of blackjack from a fixed-seed shuffled deck and prints the final totals of the player and dealer.
import random
from typing import List, Tuple

RANKS: List[str] = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS: List[str] = ["Clubs", "Diamonds", "Hearts", "Spades"]


def build_deck() -> List[Tuple[str, str]]:
    return [(rank, suit) for suit in SUITS for rank in RANKS]


def card_value(rank: str) -> int:
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_total(hand: List[Tuple[str, str]]) -> int:
    total = sum(card_value(rank) for rank, _ in hand)
    aces = sum(1 for rank, _ in hand if rank == "A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def format_hand(hand: List[Tuple[str, str]]) -> str:
    return ", ".join(f"{rank} of {suit}" for rank, suit in hand)


def main() -> None:
    random.seed(12345)
    deck = build_deck()
    random.shuffle(deck)

    player: List[Tuple[str, str]] = [deck.pop(), deck.pop()]
    dealer: List[Tuple[str, str]] = [deck.pop(), deck.pop()]

    # Player strategy: hit until total reaches at least 17.
    while hand_total(player) < 17:
        player.append(deck.pop())

    player_total = hand_total(player)
    print(f"Player hand: {format_hand(player)}")

    if player_total > 21:
        print("Player busts.")
        print(f"Player total: {player_total}")
        print(f"Dealer hand: {format_hand(dealer)}")
        print(f"Dealer total: {hand_total(dealer)}")
        return

    # Dealer strategy: hit until total reaches at least 17.
    while hand_total(dealer) < 17:
        dealer.append(deck.pop())

    dealer_total = hand_total(dealer)
    print(f"Dealer hand: {format_hand(dealer)}")

    print(f"Player total: {player_total}")
    print(f"Dealer total: {dealer_total}")

    if dealer_total > 21:
        print("Dealer busts. Player wins.")
    elif player_total > dealer_total:
        print("Player wins.")
    elif player_total < dealer_total:
        print("Dealer wins.")
    else:
        print("Push.")


if __name__ == "__main__":
    main()
