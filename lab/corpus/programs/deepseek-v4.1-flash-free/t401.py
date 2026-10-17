import sys
from collections import Counter

RANK_ORDER = "23456789TJQKA"
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANK_ORDER)}


def evaluate(cards: list[str]) -> tuple:
    ranks = sorted((RANK_VALUE[c[0]] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    counts = Counter(ranks)
    by_count = sorted(counts.items(), key=lambda kv: (-kv[1], -kv[0]))
    flush = len(set(suits)) == 1

    distinct = sorted(set(ranks), reverse=True)
    straight_high = 0
    if len(distinct) == 5:
        if distinct[0] - distinct[4] == 4:
            straight_high = distinct[0]
        elif distinct == [14, 5, 4, 3, 2]:
            straight_high = 5

    if flush and straight_high:
        return (8, straight_high)
    if by_count[0][1] == 4:
        return (7, by_count[0][0], by_count[1][0])
    if by_count[0][1] == 3 and by_count[1][1] == 2:
        return (6, by_count[0][0], by_count[1][0])
    if flush:
        return (5, *ranks)
    if straight_high:
        return (4, straight_high)
    if by_count[0][1] == 3:
        return (3, by_count[0][0], by_count[1][0], by_count[2][0])
    if by_count[0][1] == 2 and by_count[1][1] == 2:
        return (2, by_count[0][0], by_count[1][0], by_count[2][0])
    if by_count[0][1] == 2:
        return (1, by_count[0][0], by_count[1][0], by_count[2][0], by_count[3][0])
    return (0, *ranks)


def main() -> None:
    hands = [line.split() for line in sys.stdin if line.strip()]
    out: list[str] = []
    for i in range(0, len(hands) - 1, 2):
        a, b = evaluate(hands[i]), evaluate(hands[i + 1])
        if a > b:
            out.append(str(i + 1))
        elif b > a:
            out.append(str(i + 2))
        else:
            out.append("tie")
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


if __name__ == "__main__":
    main()
