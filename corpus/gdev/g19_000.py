# task: Compute the number of days between two fixed calendar dates, such as 2000-01-01 and 2024-07-15, and print the result.
from datetime import date


def days_between(start: date, end: date) -> int:
    """Return the number of days from start to end (negative if end is earlier)."""
    return (end - start).days


def main() -> None:
    start = date(2000, 1, 1)
    end = date(2024, 7, 15)
    result = days_between(start, end)
    print(f"Days between {start.isoformat()} and {end.isoformat()}: {result}")


if __name__ == "__main__":
    main()
