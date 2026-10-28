# task: Count the number of weekdays and weekend days between 2024-01-01 and 2024-12-31 and print both totals.
from datetime import date, timedelta


def count_weekdays_and_weekend(start: date, end: date) -> tuple[int, int]:
    """Return (weekday_count, weekend_count) for the inclusive date range."""
    weekdays = 0
    weekend = 0
    current = start
    one_day = timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:  # Monday=0 .. Friday=4
            weekdays += 1
        else:  # Saturday=5, Sunday=6
            weekend += 1
        current += one_day
    return weekdays, weekend


def main() -> None:
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    weekdays, weekend = count_weekdays_and_weekend(start, end)
    print(f"Weekdays: {weekdays}")
    print(f"Weekend days: {weekend}")


if __name__ == "__main__":
    main()
