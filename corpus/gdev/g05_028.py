# task: Tally the Roman numeral symbols used when writing the integers 1 through 100 and print the totals for each symbol.
from collections import Counter

ROMAN_TABLE: list[tuple[int, str]] = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]

SYMBOL_ORDER: str = "IVXLCDM"


def to_roman(number: int) -> str:
    """Convert a positive integer to its standard Roman numeral form."""
    parts: list[str] = []
    remaining = number
    for value, symbol in ROMAN_TABLE:
        while remaining >= value:
            parts.append(symbol)
            remaining -= value
    return "".join(parts)


def count_symbols(limit: int) -> Counter[str]:
    """Count every Roman numeral symbol used when writing 1 through limit."""
    counts: Counter[str] = Counter()
    for number in range(1, limit + 1):
        for symbol in to_roman(number):
            counts[symbol] += 1
    return counts


def main() -> None:
    totals = count_symbols(100)
    print("Roman numeral symbol totals for 1 through 100:")
    for symbol in SYMBOL_ORDER:
        print(f"{symbol}: {totals[symbol]}")
    print(f"Total symbols: {sum(totals.values())}")


if __name__ == "__main__":
    main()
