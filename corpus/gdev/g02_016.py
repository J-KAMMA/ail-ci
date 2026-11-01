# task: Convert 2024 to Roman numerals with a greedy algorithm, convert the result back to an integer, and print both.
from typing import Final

ROMAN_VALUES: Final[list[tuple[int, str]]] = [
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

ROMAN_DIGIT_VALUES: Final[dict[str, int]] = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}


def int_to_roman(number: int) -> str:
    """Convert a positive integer to a Roman numeral using a greedy algorithm."""
    if number <= 0:
        raise ValueError("Roman numerals require a positive integer.")
    remaining: int = number
    parts: list[str] = []
    for value, symbol in ROMAN_VALUES:
        count, remaining = divmod(remaining, value)
        parts.append(symbol * count)
    return "".join(parts)


def roman_to_int(numeral: str) -> int:
    """Convert a Roman numeral string to an integer."""
    total: int = 0
    previous: int = 0
    for char in reversed(numeral.upper()):
        if char not in ROMAN_DIGIT_VALUES:
            raise ValueError(f"Invalid Roman numeral character: {char!r}")
        value: int = ROMAN_DIGIT_VALUES[char]
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    return total


def main() -> None:
    year: int = 2024
    roman: str = int_to_roman(year)
    back: int = roman_to_int(roman)
    print(f"Roman numeral for {year}: {roman}")
    print(f"Converted back to integer: {back}")


if __name__ == "__main__":
    main()
