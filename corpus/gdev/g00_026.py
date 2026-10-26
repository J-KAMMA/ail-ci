# task: Write a script that checks whether two hardcoded strings are anagrams of each other, ignoring whitespace and case, and prints the result.
from collections import Counter


def normalize(text: str) -> str:
    """Lowercase the text and remove all whitespace characters."""
    return "".join(ch.lower() for ch in text if not ch.isspace())


def are_anagrams(first: str, second: str) -> bool:
    """Return True if the two strings are anagrams, ignoring whitespace and case."""
    return Counter(normalize(first)) == Counter(normalize(second))


def main() -> None:
    first: str = "Dormitory"
    second: str = "Dirty room"

    result: bool = are_anagrams(first, second)

    print(f"First string:  {first!r}")
    print(f"Second string: {second!r}")
    print(f"Are anagrams (ignoring whitespace and case): {result}")


if __name__ == "__main__":
    main()
