# task: Compute all modes of a fixed list of integers using a frequency dictionary and print them in ascending order.
from collections import Counter
from typing import Dict, List


def compute_frequencies(values: List[int]) -> Dict[int, int]:
    """Build a frequency dictionary mapping each value to its count."""
    freq: Dict[int, int] = {}
    for value in values:
        freq[value] = freq.get(value, 0) + 1
    return freq


def compute_modes(values: List[int]) -> List[int]:
    """Return all modes (values with maximum frequency) in ascending order."""
    if not values:
        return []
    freq = compute_frequencies(values)
    max_count = max(freq.values())
    modes = [value for value, count in freq.items() if count == max_count]
    return sorted(modes)


def main() -> None:
    data: List[int] = [4, 1, 2, 2, 3, 4, 5, 1, 6, 4, 1, 7, 7, 2, 8, 8, 8, 0, 3, 3, 9, 9]
    freq = compute_frequencies(data)
    print("Frequency dictionary (sorted by value):")
    for value in sorted(freq):
        print(f"  {value}: {freq[value]}")

    modes = compute_modes(data)
    print("Modes in ascending order:", ", ".join(str(m) for m in modes))

    # Cross-check against the standard library's Counter.
    counter_modes = sorted(
        v for v, c in Counter(data).items() if c == max(Counter(data).values())
    )
    print("Cross-check matches:", modes == counter_modes)


if __name__ == "__main__":
    main()
