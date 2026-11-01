# task: Use Counter to find the index of the first non-repeating character in a hardcoded string and print it.
from collections import Counter


def first_non_repeating_index(text: str) -> int:
    """Return the index of the first character that appears exactly once, or -1 if none."""
    counts: Counter[str] = Counter(text)
    for index, char in enumerate(text):
        if counts[char] == 1:
            return index
    return -1


def main() -> None:
    text: str = "swiss programming"
    index: int = first_non_repeating_index(text)
    if index == -1:
        print("No non-repeating character found.")
    else:
        print(index)


if __name__ == "__main__":
    main()
