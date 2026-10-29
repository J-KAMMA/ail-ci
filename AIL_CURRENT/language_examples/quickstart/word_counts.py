def summarize(words: list[str]) -> None:
    counts: dict[str, int] = {}
    total = 0
    for word in words:
        counts[word] = counts.get(word, 0) + 1
        total += len(word)
    for word in sorted(counts):
        print(word, counts[word])
    print("total letters:", total)


def main() -> None:
    words = ["apple", "pear", "apple", "fig"]
    summarize(words)


main()
