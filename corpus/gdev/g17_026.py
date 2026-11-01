# task: Sort a list of strings by their count of distinct vowels, breaking ties alphabetically.
from typing import Final

VOWELS: Final[frozenset[str]] = frozenset("aeiou")


def distinct_vowel_count(text: str) -> int:
    """Return the number of distinct vowels (a, e, i, o, u) in text, ignoring case."""
    return len({ch for ch in text.lower() if ch in VOWELS})


def sort_by_distinct_vowels(words: list[str]) -> list[str]:
    """Sort by distinct vowel count ascending, breaking ties alphabetically."""
    return sorted(words, key=lambda w: (distinct_vowel_count(w), w))


def main() -> None:
    words: list[str] = [
        "banana",
        "sky",
        "queue",
        "education",
        "rhythm",
        "apple",
        "audio",
        "tree",
        "cat",
        "moon",
        "Aeon",
        "bee",
        "strengths",
        "onomatopoeia",
    ]

    for word in sort_by_distinct_vowels(words):
        print(f"{distinct_vowel_count(word)}  {word}")


if __name__ == "__main__":
    main()
