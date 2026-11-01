# task: Write a script that uses re.sub with a dictionary-driven callable to expand hardcoded abbreviations such as 'Dr.' and 'St.' in an address list and prints the expanded text.
import re
from typing import Final

ABBREVIATIONS: Final[dict[str, str]] = {
    "Dr": "Doctor",
    "St": "Street",
    "Ave": "Avenue",
    "Blvd": "Boulevard",
    "Rd": "Road",
    "Mr": "Mister",
    "Mrs": "Missus",
    "Ms": "Miss",
    "Ln": "Lane",
    "Apt": "Apartment",
}

ADDRESSES: Final[list[str]] = [
    "Dr. Alice Moreno, 12 Main St. Apt. 4, Springfield",
    "Mr. Bob Chen, 88 Oak Ave., Riverton",
    "Mrs. Dana Ross, 301 Elm Blvd., Lakeside",
    "Ms. Priya Nair, 7 Pine Rd., Hillcrest",
    "Dr. Samuel Okafor, 45 Cedar Ln., Brookfield",
]


def build_pattern(abbreviations: dict[str, str]) -> re.Pattern[str]:
    # Longer keys first so that alternation prefers the longest match.
    keys = sorted(abbreviations, key=len, reverse=True)
    alternation = "|".join(re.escape(key) for key in keys)
    return re.compile(rf"\b({alternation})\.")


def make_expander(abbreviations: dict[str, str]):
    def expand(match: re.Match[str]) -> str:
        return abbreviations[match.group(1)]

    return expand


def expand_text(text: str, pattern: re.Pattern[str], abbreviations: dict[str, str]) -> str:
    return pattern.sub(make_expander(abbreviations), text)


def main() -> None:
    pattern = build_pattern(ABBREVIATIONS)
    for line in ADDRESSES:
        print(expand_text(line, pattern, ABBREVIATIONS))


if __name__ == "__main__":
    main()
