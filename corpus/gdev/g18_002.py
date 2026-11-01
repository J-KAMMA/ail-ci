# task: Count word frequencies in a hardcoded paragraph with Counter and print the five most common words with their counts.
import re
from collections import Counter

PARAGRAPH: str = (
    "The quick brown fox jumps over the lazy dog. The dog barks, and the fox runs away. "
    "A quick decision by the fox saved the day, but the lazy dog slept through it all. "
    "Over the hills and far away, the brown fox found a new den. The dog never learned "
    "its lesson, and the fox never stopped being quick. In the end, the fox and the dog "
    "became unlikely friends, sharing the sun and the grass over many quiet afternoons."
)

TOP_N: int = 5


def tokenize(text: str) -> list[str]:
    """Return lowercase words consisting of letters and apostrophes."""
    return re.findall(r"[a-z']+", text.lower())


def main() -> None:
    words: list[str] = tokenize(PARAGRAPH)
    counts: Counter[str] = Counter(words)

    # Sort by descending count, then alphabetically, so ties are deterministic.
    top: list[tuple[str, int]] = sorted(
        counts.items(), key=lambda item: (-item[1], item[0])
    )[:TOP_N]

    print(f"Total words: {len(words)}")
    print(f"Unique words: {len(counts)}")
    print(f"Top {TOP_N} most common words:")
    for rank, (word, count) in enumerate(top, start=1):
        print(f"{rank}. {word}: {count}")


if __name__ == "__main__":
    main()
