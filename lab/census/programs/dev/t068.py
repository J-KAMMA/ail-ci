import sys


PUNCTUATION = ",.!;"


def main() -> None:
    words: set[str] = set()
    for line in sys.stdin:
        for token in line.split():
            cleaned = "".join(ch for ch in token if ch not in PUNCTUATION).lower()
            if cleaned:
                words.add(cleaned)
    for word in sorted(words):
        print(word)


if __name__ == "__main__":
    main()
