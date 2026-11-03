# task: Use Counter arithmetic to find which letters appear more often in one hardcoded word than in another and print the differences.
from collections import Counter


WORD_A: str = "banana"
WORD_B: str = "orange"


def describe_differences(label: str, diff: Counter[str]) -> None:
    """Print the letters in a Counter difference, sorted alphabetically."""
    print(label)
    if not diff:
        print("  (none)")
        return
    for letter in sorted(diff):
        print(f"  {letter!r}: {diff[letter]}")


def main() -> None:
    counts_a: Counter[str] = Counter(WORD_A)
    counts_b: Counter[str] = Counter(WORD_B)

    # Counter subtraction keeps only positive counts.
    more_in_a: Counter[str] = counts_a - counts_b
    more_in_b: Counter[str] = counts_b - counts_a

    print(f"Word A: {WORD_A}")
    print(f"Word B: {WORD_B}")
    print()
    describe_differences(f"Letters more frequent in '{WORD_A}' than in '{WORD_B}':", more_in_a)
    print()
    describe_differences(f"Letters more frequent in '{WORD_B}' than in '{WORD_A}':", more_in_b)


if __name__ == "__main__":
    main()
