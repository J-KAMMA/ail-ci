# task: Determine the number of minutes until the next full hour from the fixed time 2024-03-15 13:42:17 and print the value.
from datetime import datetime, timedelta


def minutes_until_next_full_hour(now: datetime) -> float:
    """Return the minutes remaining until the next full hour after `now`."""
    truncated = now.replace(minute=0, second=0, microsecond=0)
    next_full_hour = truncated + timedelta(hours=1)
    remaining: timedelta = next_full_hour - now
    return remaining.total_seconds() / 60.0


def main() -> None:
    fixed_now = datetime(2024, 3, 15, 13, 42, 17)
    minutes = minutes_until_next_full_hour(fixed_now)
    print(f"{minutes:.4f}")


if __name__ == "__main__":
    main()
