# task: Count the frequency of each character in a hard-coded sentence and print the counts sorted alphabetically.
from collections import Counter

SENTENCE: str = "The quick brown fox jumps over the lazy dog, and then it sleeps!"


def main() -> None:
    counts: Counter[str] = Counter(SENTENCE)
    # Sort alphabetically, ignoring case, with the original character as a tie-breaker.
    for char in sorted(counts, key=lambda c: (c.lower(), c)):
        print(f"{char!r}: {counts[char]}")


if __name__ == "__main__":
    main()
