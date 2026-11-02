# task: Sort a fixed list of strings by length and then alphabetically using a custom key function and print the ordering.
from typing import Sequence


WORDS: list[str] = [
    "banana",
    "kiwi",
    "apple",
    "fig",
    "cherry",
    "date",
    "elderberry",
    "grape",
    "lime",
    "mango",
    "nectarine",
    "pear",
]


def sort_key(word: str) -> tuple[int, str]:
    """Sort primarily by length, then alphabetically (case-insensitive)."""
    return (len(word), word.lower())


def sort_words(words: Sequence[str]) -> list[str]:
    """Return a new list of words ordered by the custom key."""
    return sorted(words, key=sort_key)


def main() -> None:
    ordered = sort_words(WORDS)
    print("Sorted by length, then alphabetically:")
    for index, word in enumerate(ordered, start=1):
        print(f"{index:2d}. {word} (length {len(word)})")


if __name__ == "__main__":
    main()
