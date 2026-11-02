# task: Use Counter subtraction to determine which letters must be added to one fixed string to form another fixed string.
from collections import Counter


def letters_to_add(base: str, target: str) -> Counter[str]:
    """Return the letters that must be added to base to form target."""
    return Counter(target) - Counter(base)


def letters_to_remove(base: str, target: str) -> Counter[str]:
    """Return the letters that would be left over from base after forming target."""
    return Counter(base) - Counter(target)


def format_counter(counts: Counter[str]) -> str:
    """Format a Counter deterministically, sorted by letter."""
    if not counts:
        return "(none)"
    return ", ".join(f"{ch!r} x{n}" for ch, n in sorted(counts.items()))


def main() -> None:
    base: str = "rain"
    target: str = "train in spring"

    to_add = letters_to_add(base, target)
    to_remove = letters_to_remove(base, target)

    print(f"Base string:   {base!r}")
    print(f"Target string: {target!r}")
    print()
    print("Letters that must be added to the base:")
    print(f"  {format_counter(to_add)}")
    print(f"  Total added: {sum(to_add.values())}")
    print()
    print("Letters in the base not needed for the target:")
    print(f"  {format_counter(to_remove)}")
    print(f"  Total surplus: {sum(to_remove.values())}")
    print()

    rebuilt = Counter(base) + to_add
    print("Check: base + additions equals target letter counts:",
          rebuilt == Counter(target) + (Counter(base) - Counter(base)))


if __name__ == "__main__":
    main()
