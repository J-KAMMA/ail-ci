# task: Filter palindromes from a fixed word list and sort the survivors by length descending.
from __future__ import annotations


WORD_LIST: list[str] = [
    "level",
    "python",
    "racecar",
    "noon",
    "algorithm",
    "Deified",
    "stats",
    "palindrome",
    "Kayak",
    "refer",
    "hello",
    "Madam",
    "rotator",
    "computer",
    "a",
    "redder",
    "sagas",
    "Racecar",
    "abcba",
    "xyz",
    "reviver",
    "",
    "No lemon",
    "wow",
]


def is_palindrome(word: str) -> bool:
    """Return True if the word reads the same forwards and backwards, ignoring case."""
    normalized: str = word.lower()
    return len(normalized) > 0 and normalized == normalized[::-1]


def filter_palindromes(words: list[str]) -> list[str]:
    """Return only the palindromic words from the input list, preserving order."""
    return [word for word in words if is_palindrome(word)]


def sort_by_length_desc(words: list[str]) -> list[str]:
    """Sort words by length descending; ties broken alphabetically (case-insensitive, then exact)."""
    return sorted(words, key=lambda w: (-len(w), w.lower(), w))


def main() -> None:
    palindromes: list[str] = filter_palindromes(WORD_LIST)
    ordered: list[str] = sort_by_length_desc(palindromes)

    print(f"Found {len(ordered)} palindromes:")
    for word in ordered:
        print(f"{len(word):>3}  {word}")


if __name__ == "__main__":
    main()
