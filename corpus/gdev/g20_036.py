# task: Write a script that uses re.match to validate hardcoded Roman numerals and prints the decimal value of each valid one.
import re
from typing import Final

ROMAN_PATTERN: Final = re.compile(
    r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})\Z"
)

ROMAN_VALUES: Final[dict[str, int]] = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}

CANDIDATES: Final[tuple[str, ...]] = (
    "III",
    "IV",
    "IX",
    "LVIII",
    "MCMXCIV",
    "MMXXIV",
    "MMMCMXCIX",
    "XLII",
    "CDXLIV",
    "IIII",
    "VX",
    "IC",
    "MMMM",
    "",
    "mcm",
    "XXXX",
)


def is_valid_roman(numeral: str) -> bool:
    """Return True if the string is a well-formed Roman numeral."""
    if not numeral:
        return False
    return ROMAN_PATTERN.match(numeral) is not None


def roman_to_int(numeral: str) -> int:
    """Convert a valid Roman numeral to its decimal value."""
    total = 0
    for index, symbol in enumerate(numeral):
        value = ROMAN_VALUES[symbol]
        if index + 1 < len(numeral) and ROMAN_VALUES[numeral[index + 1]] > value:
            total -= value
        else:
            total += value
    return total


def main() -> None:
    for candidate in CANDIDATES:
        if is_valid_roman(candidate):
            print(f"{candidate} -> {roman_to_int(candidate)}")


if __name__ == "__main__":
    main()
