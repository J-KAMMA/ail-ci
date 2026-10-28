# task: Determine whether two fixed strings are anagrams by comparing their character count dictionaries.
from collections import Counter


def char_counts(text: str) -> dict[str, int]:
    """Return a dictionary mapping each character to its occurrence count."""
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    return counts


def are_anagrams(first: str, second: str) -> bool:
    """Two strings are anagrams if their character count dictionaries match."""
    return char_counts(first) == char_counts(second)


def describe_difference(first: str, second: str) -> str:
    """Explain which characters differ in count between the two strings."""
    counts_a = char_counts(first)
    counts_b = char_counts(second)
    all_chars = sorted(set(counts_a) | set(counts_b))
    diffs: list[str] = []
    for ch in all_chars:
        a = counts_a.get(ch, 0)
        b = counts_b.get(ch, 0)
        if a != b:
            diffs.append(f"{ch!r}: {a} vs {b}")
    return "; ".join(diffs)


def main() -> None:
    pairs: list[tuple[str, str]] = [
        ("listen", "silent"),
        ("triangle", "integral"),
        ("apple", "papel"),
        ("rat", "car"),
        ("Dormitory", "dirty room"),
        ("hello", "bello"),
        ("aabbcc", "abcabc"),
        ("", ""),
    ]

    for first, second in pairs:
        result = are_anagrams(first, second)
        print(f"{first!r} and {second!r}: {'anagrams' if result else 'not anagrams'}")
        if not result:
            print(f"  differences -> {describe_difference(first, second)}")

    counter_check = Counter("listen") == Counter("silent")
    print(f"Counter cross-check for 'listen'/'silent': {counter_check}")


if __name__ == "__main__":
    main()
