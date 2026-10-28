# task: Detect the first non-repeating character in a fixed string using a character count dictionary.
from typing import Optional


def count_characters(text: str) -> dict[str, int]:
    """Build a dictionary mapping each character to its occurrence count."""
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    return counts


def first_non_repeating(text: str) -> Optional[tuple[int, str]]:
    """Return (index, character) of the first non-repeating character, or None."""
    counts = count_characters(text)
    for index, ch in enumerate(text):
        if counts[ch] == 1:
            return index, ch
    return None


def main() -> None:
    sample = "swiss mississippi programming"
    print(f"Input string: {sample!r}")

    counts = count_characters(sample)
    print("Character counts (in order of first appearance):")
    for ch, n in counts.items():
        print(f"  {ch!r}: {n}")

    result = first_non_repeating(sample)
    if result is None:
        print("No non-repeating character found.")
    else:
        index, ch = result
        print(f"First non-repeating character: {ch!r} at index {index}")


if __name__ == "__main__":
    main()
