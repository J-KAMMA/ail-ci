# task: Print a countdown in days, hours, and minutes from the fixed moment 2024-01-01 00:00:00 to 2024-12-25 18:30:00.
from datetime import datetime, timedelta

START: datetime = datetime(2024, 1, 1, 0, 0, 0)
TARGET: datetime = datetime(2024, 12, 25, 18, 30, 0)


def format_countdown(delta: timedelta) -> str:
    """Format a non-negative timedelta as days, hours, and minutes."""
    total_minutes: int = int(delta.total_seconds()) // 60
    days, remainder = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remainder, 60)
    return f"{days} days, {hours} hours, {minutes} minutes"


def main() -> None:
    remaining: timedelta = TARGET - START
    print(f"Countdown from {START:%Y-%m-%d %H:%M:%S} to {TARGET:%Y-%m-%d %H:%M:%S}:")
    print(format_countdown(remaining))


if __name__ == "__main__":
    main()
