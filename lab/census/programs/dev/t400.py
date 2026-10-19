from collections import Counter
import sys

RANK_VALUES: dict[str, int] = {r: i for i, r in enumerate("23456789TJQKA", start=2)}


def analyze_hand(cards: list[str]) -> tuple[list[str], bool]:
    ranks = [card[0] for card in cards]
    suits = [card[1] for card in cards]
    counts = Counter(ranks)
    ordered = sorted(
        ranks,
        key=lambda r: (counts[r], RANK_VALUES[r]),
        reverse=True,
    )
    is_flush = len(set(suits)) == 1
    return ordered, is_flush


def main() -> None:
    output_lines: list[str] = []
    for line in sys.stdin:
        cards = line.split()
        if not cards:
            continue
        ordered, is_flush = analyze_hand(cards)
        output_lines.append(f"{' '.join(ordered)} {is_flush}")
    if output_lines:
        print("\n".join(output_lines))


if __name__ == "__main__":
    main()
