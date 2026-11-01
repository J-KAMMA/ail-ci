# task: Use a set comprehension to extract the unique vowels from a fixed paragraph and print them in sorted order.
from typing import Final

PARAGRAPH: Final[str] = (
    "The quick brown fox jumps over the lazy dog. "
    "Programming in Python is an elegant way to explore ideas, "
    "and every evening we often read about old algorithms and "
    "unusual architectures."
)

VOWELS: Final[frozenset[str]] = frozenset("aeiou")


def unique_vowels(text: str) -> list[str]:
    """Return the unique vowels found in text, sorted alphabetically."""
    found: set[str] = {ch for ch in text.lower() if ch in VOWELS}
    return sorted(found)


def main() -> None:
    vowels = unique_vowels(PARAGRAPH)
    print("Unique vowels:", ", ".join(vowels))


if __name__ == "__main__":
    main()
