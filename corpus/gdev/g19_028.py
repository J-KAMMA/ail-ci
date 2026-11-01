# task: Compute the midpoint datetime between 2024-01-01 08:00 and 2024-01-03 20:00 and print it.
from datetime import datetime, timedelta


def midpoint(start: datetime, end: datetime) -> datetime:
    """Return the datetime exactly halfway between start and end."""
    return start + (end - start) / 2


def main() -> None:
    start: datetime = datetime(2024, 1, 1, 8, 0)
    end: datetime = datetime(2024, 1, 3, 20, 0)
    mid: datetime = midpoint(start, end)
    print(mid.isoformat())


if __name__ == "__main__":
    main()
