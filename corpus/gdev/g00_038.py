# task: Write a script that finds all occurrences and starting indices of a hardcoded pattern in a hardcoded text, including overlapping matches.
from typing import List


TEXT: str = "abracadabra abracadabra ababab aaaa"
PATTERN: str = "aba"


def find_all_occurrences(text: str, pattern: str) -> List[int]:
    """Return every starting index where pattern occurs in text, including overlaps."""
    if not pattern:
        return []
    indices: List[int] = []
    start: int = 0
    while True:
        index: int = text.find(pattern, start)
        if index == -1:
            break
        indices.append(index)
        start = index + 1
    return indices


def main() -> None:
    indices: List[int] = find_all_occurrences(TEXT, PATTERN)
    print(f"Text: {TEXT!r}")
    print(f"Pattern: {PATTERN!r}")
    print(f"Number of occurrences: {len(indices)}")
    for position, index in enumerate(indices, start=1):
        print(f"Match {position}: starts at index {index}")
    if indices:
        print(f"Starting indices: {indices}")
    else:
        print("Starting indices: []")


if __name__ == "__main__":
    main()
