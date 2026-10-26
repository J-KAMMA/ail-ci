# task: Find the first Monday of every month in 2024 and print each date in ISO format.
from datetime import date, timedelta


def first_monday(year: int, month: int) -> date:
    """Return the first Monday of the given year and month."""
    first_day = date(year, month, 1)
    # Monday is weekday 0 in Python's date.weekday()
    days_until_monday = (0 - first_day.weekday()) % 7
    return first_day + timedelta(days=days_until_monday)


def main() -> None:
    for month in range(1, 13):
        print(first_monday(2024, month).isoformat())


if __name__ == "__main__":
    main()
