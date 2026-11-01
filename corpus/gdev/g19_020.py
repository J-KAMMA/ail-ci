# task: Print the day of the year (ordinal day) for several fixed dates such as 2024-03-01 and 2024-12-31.
from datetime import date


def day_of_year(d: date) -> int:
    """Return the ordinal day of the year (1-based) for a date."""
    return d.timetuple().tm_yday


def main() -> None:
    fixed_dates: list[date] = [
        date(2024, 1, 1),
        date(2024, 3, 1),
        date(2024, 7, 4),
        date(2024, 12, 31),
        date(2023, 3, 1),
        date(2023, 12, 31),
        date(2000, 2, 29),
    ]

    for d in fixed_dates:
        print(f"{d.isoformat()}: day {day_of_year(d)} of the year")


if __name__ == "__main__":
    main()
