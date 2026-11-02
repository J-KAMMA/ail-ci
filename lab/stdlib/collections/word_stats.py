from collections import Counter


def words(text: str) -> list[str]:
    out = []
    for raw in text.lower().split():
        word = raw.strip(".,;:!?")
        if word:
            out.append(word)
    return out


def main() -> int:
    text = "The quick brown fox. The lazy dog; the fox runs, the dog sleeps!"
    counts = Counter(words(text))
    print(len(counts), sum(counts.values()))
    for word, n in counts.most_common(3):
        print(word, n)
    print(counts["the"], counts["missing"])
    counts.update(["fox", "cat", "the"])
    counts["dog"] -= 1
    del counts["quick"]
    del counts["absent"]
    print(counts.most_common())
    print(counts.total(), sorted(counts.elements()))
    other = Counter("the fox and the hound")
    print(sorted((counts + other).items()))
    print(sorted((counts - other).items()))
    print(sorted((counts & other).items()))
    print(sorted((counts | other).items()))
    empty: Counter[str] = Counter()
    print(empty, len(empty), empty.total(), empty.most_common())
    empty.update("aa")
    print(empty)
    return 0


main()
