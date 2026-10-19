from collections import Counter


def main() -> None:
    line = input() if True else ""
    words: list[str] = line.split()

    word_counts = Counter(words)
    ordered_words = sorted(word_counts.items(), key=lambda item: (-item[1], item[0]))
    for word, count in ordered_words:
        print(f"{word}={count}")

    bigram_counts: Counter[tuple[str, str]] = Counter(
        (words[i], words[i + 1]) for i in range(len(words) - 1)
    )
    ordered_bigrams = sorted(bigram_counts.items(), key=lambda item: (-item[1], item[0]))
    for (first, second), count in ordered_bigrams[:3]:
        print(f"{first} {second}={count}")


if __name__ == "__main__":
    main()
