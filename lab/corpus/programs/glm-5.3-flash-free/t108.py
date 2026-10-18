import sys
from collections import Counter
from typing import List, Tuple


def main() -> None:
    line: str = sys.stdin.readline()
    words: List[str] = line.split()

    word_counts: Counter[str] = Counter(words)
    for word, count in sorted(word_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{word}={count}")

    bigrams: List[Tuple[str, str]] = list(zip(words, words[1:]))
    bigram_counts: Counter[Tuple[str, str]] = Counter(bigrams)
    top_bigrams = sorted(bigram_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    for (w1, w2), count in top_bigrams:
        print(f"{w1} {w2}={count}")


if __name__ == "__main__":
    main()
