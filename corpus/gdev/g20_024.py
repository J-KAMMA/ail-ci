# task: Write a script that uses re.findall with a word boundary pattern to count how many times each hardcoded target word appears in a paragraph, ignoring case.
import re
from collections import Counter


TARGET_WORDS: list[str] = [
    "the",
    "fox",
    "dog",
    "quick",
    "lazy",
    "and",
    "run",
]

PARAGRAPH: str = (
    "The quick brown fox jumps over the lazy dog. The dog sleeps while the fox "
    "runs away, and the fox is quick. Behind the barn, the dog and the fox "
    "run and run, while the lazy cat watches the quick chase from the fence."
)


def count_target_words(text: str, targets: list[str]) -> dict[str, int]:
    """Count case-insensitive whole-word occurrences of each target word."""
    lowered = text.lower()
    found: Counter[str] = Counter(re.findall(r"\b\w+\b", lowered))
    return {word: found[word.lower()] for word in targets}


def main() -> None:
    counts = count_target_words(PARAGRAPH, TARGET_WORDS)
    for word in TARGET_WORDS:
        print(f"{word}: {counts[word]}")


if __name__ == "__main__":
    main()
