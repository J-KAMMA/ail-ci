# task: Generate and print all leap years between 1900 and 2100 using a datetime-based leap check.
from datetime import date


def is_leap_year(year: int) -> bool:
    """Return True if the year is a leap year, using datetime to test for Feb 29."""
    try:
        date(year, 2, 29)
    except ValueError:
        return False
    return True


def main() -> None:
    start: int = 1900
    end: int = 2100
    leap_years: list[int] = [y for y in range(start, end + 1) if is_leap_year(y)]
    for year in leap_years:
        print(year)


if __name__ == "__main__":
    main()
