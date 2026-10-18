import sys
from collections import Counter


def main() -> None:
    words = sys.stdin.readline().split()

    word_counts = Counter(words)
    for word, count in sorted(word_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{word}={count}")

    bigram_counts = Counter(zip(words, words[1:]))
    top_bigrams = sorted(bigram_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    for (first, second), count in top_bigrams:
        print(f"{first} {second}={count}")


if __name__ == "__main__":
    main()
