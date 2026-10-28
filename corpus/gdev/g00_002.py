# task: Write a script that checks whether each string in a hardcoded list is a palindrome after removing non-alphanumeric characters, and prints each verdict.
from typing import Iterable


PHRASES: list[str] = [
    "A man, a plan, a canal: Panama",
    "racecar",
    "Was it a car or a cat I saw?",
    "No lemon, no melon",
    "Hello, World!",
    "",
    "12321",
    "Not a palindrome 123",
    "Able was I, ere I saw Elba!",
    "Madam, in Eden, I'm Adam",
]


def normalize(text: str) -> str:
    """Return the text lowercased with only alphanumeric characters kept."""
    return "".join(ch.lower() for ch in text if ch.isalnum())


def is_palindrome(text: str) -> bool:
    """Check whether the normalized text reads the same forwards and backwards."""
    cleaned = normalize(text)
    return cleaned == cleaned[::-1]


def report(phrases: Iterable[str]) -> None:
    """Print a verdict line for each phrase, in list order."""
    for index, phrase in enumerate(phrases, start=1):
        verdict = "PALINDROME" if is_palindrome(phrase) else "NOT A PALINDROME"
        print(f"{index:2d}. {phrase!r}: {verdict}")


def main() -> None:
    report(PHRASES)


if __name__ == "__main__":
    main()
