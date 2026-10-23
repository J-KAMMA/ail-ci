# task: Format the fixed datetime 2024-06-01 14:05:09 in several strftime patterns and print each result.
from datetime import datetime


def main() -> None:
    moment: datetime = datetime(2024, 6, 1, 14, 5, 9)

    patterns: list[tuple[str, str]] = [
        ("ISO-like date", "%Y-%m-%d"),
        ("Date and time", "%Y-%m-%d %H:%M:%S"),
        ("US date", "%m/%d/%Y"),
        ("European date", "%d.%m.%Y"),
        ("12-hour clock", "%I:%M:%S %p"),
        ("24-hour time", "%H:%M"),
        ("Full weekday and month", "%A, %B %d, %Y"),
        ("Abbreviated weekday", "%a %b %e %Y"),
        ("Day of year", "%Y-%j"),
        ("ISO week", "%G-W%V-%u"),
        ("Compact timestamp", "%Y%m%dT%H%M%S"),
        ("Literal percent with time", "%H%% done at %M min"),
    ]

    for label, pattern in patterns:
        print(f"{label}: {moment.strftime(pattern)}")


if __name__ == "__main__":
    main()
