# task: Build a dictionary mapping each character in a fixed string to the list of its positions and print characters that appear more than once.
from typing import Dict, List


def build_positions(text: str) -> Dict[str, List[int]]:
    positions: Dict[str, List[int]] = {}
    for index, char in enumerate(text):
        positions.setdefault(char, []).append(index)
    return positions


def main() -> None:
    text: str = "the quick brown fox jumps over the lazy dog, then it sleeps"
    positions: Dict[str, List[int]] = build_positions(text)

    print(f"Text: {text!r}")
    print(f"Length: {len(text)}")
    print(f"Distinct characters: {len(positions)}")
    print("Characters appearing more than once:")

    repeated = [ch for ch in sorted(positions) if len(positions[ch]) > 1]
    for ch in repeated:
        print(f"  {ch!r}: {len(positions[ch])} times at positions {positions[ch]}")

    if not repeated:
        print("  (none)")


if __name__ == "__main__":
    main()
