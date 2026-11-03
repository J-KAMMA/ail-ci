# task: Parse a list of date strings with datetime.strptime, catch ValueError, and list the positions of all invalid entries.
from datetime import datetime
from typing import Final

DATE_FORMAT: Final[str] = "%Y-%m-%d"

SAMPLE_DATES: Final[list[str]] = [
    "2024-01-15",
    "2023-02-29",
    "2024-02-29",
    "not a date",
    "2022-13-01",
    "1999-12-31",
    "",
    "2020-06-15",
    "2021-04-31",
    "20-05-2021",
]


def parse_dates(values: list[str], fmt: str) -> tuple[list[datetime], list[int]]:
    """Parse each string; return parsed datetimes and zero-based indices of invalid entries."""
    parsed: list[datetime] = []
    invalid_positions: list[int] = []
    for position, text in enumerate(values):
        try:
            parsed.append(datetime.strptime(text, fmt))
        except ValueError:
            invalid_positions.append(position)
    return parsed, invalid_positions


def main() -> None:
    parsed, invalid_positions = parse_dates(SAMPLE_DATES, DATE_FORMAT)

    print(f"Total entries: {len(SAMPLE_DATES)}")
    print(f"Valid entries: {len(parsed)}")
    print(f"Invalid entries: {len(invalid_positions)}")
    print("Positions of invalid entries (zero-based):")
    for position in invalid_positions:
        print(f"  [{position}] {SAMPLE_DATES[position]!r}")

    if invalid_positions:
        print("Invalid positions list:", invalid_positions)
    else:
        print("Invalid positions list: []")


if __name__ == "__main__":
    main()
