import sys

RANKS = "23456789TJQKA"
RANK_VALUE = {r: i for i, r in enumerate(RANKS)}


def sort_cards(cards: list[str]) -> list[str]:
    return sorted(cards, key=lambda card: RANK_VALUE[card[0]])


def longest_run(cards: list[str]) -> list[str]:
    values = sorted({RANK_VALUE[card[0]] for card in cards})
    best: list[int] = []
    current: list[int] = []
    for value in values:
        if current and value == current[-1] + 1:
            current.append(value)
        else:
            current = [value]
        if len(current) > len(best):
            best = list(current)
    return [RANKS[value] for value in best]


def main() -> None:
    cards = sys.stdin.read().split()
    print(" ".join(sort_cards(cards)))
    print(" ".join(longest_run(cards)))


if __name__ == "__main__":
    main()
