# task: Print the number of days in each month of the year 2100, which is not a leap year, using datetime arithmetic.
from datetime import date

MONTH_NAMES: list[str] = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def days_in_month(year: int, month: int) -> int:
    """Return the number of days in the given month using date arithmetic."""
    start: date = date(year, month, 1)
    if month == 12:
        end: date = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return (end - start).days


def main() -> None:
    year: int = 2100
    for month in range(1, 13):
        days: int = days_in_month(year, month)
        print(f"{MONTH_NAMES[month - 1]}: {days}")


if __name__ == "__main__":
    main()
