# task: Write a word counter that ignores case and punctuation on a hard-coded text and prints words in descending order of frequency.
import re
from collections import Counter


TEXT = """
The quick brown fox jumps over the lazy dog. The dog barks; the fox runs!
A quick test: the fox, the dog, and the bird -- all in one sentence.
Don't stop believing, won't stop... the fox's den is quiet tonight.
The end? The END. the end!
"""


def tokenize(text: str) -> list[str]:
    """Lowercase the text and extract words, dropping punctuation."""
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)*", text.lower())


def count_words(words: list[str]) -> Counter[str]:
    """Count occurrences of each word."""
    return Counter(words)


def main() -> None:
    words = tokenize(TEXT)
    counts = count_words(words)

    # Sort by descending frequency; ties broken alphabetically for determinism.
    ordered: list[tuple[str, int]] = sorted(
        counts.items(), key=lambda item: (-item[1], item[0])
    )

    print(f"Total words: {len(words)}")
    print(f"Unique words: {len(counts)}")
    print()
    for word, count in ordered:
        print(f"{word:<12} {count}")


if __name__ == "__main__":
    main()
