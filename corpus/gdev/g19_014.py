# task: Calculate the total duration of a hard-coded list of timedelta work sessions and print it in HH:MM:SS format.
from datetime import timedelta

WORK_SESSIONS: list[timedelta] = [
    timedelta(hours=1, minutes=25, seconds=10),
    timedelta(minutes=45, seconds=30),
    timedelta(hours=2, minutes=5),
    timedelta(hours=0, minutes=59, seconds=59),
    timedelta(hours=3, minutes=12, seconds=48),
    timedelta(minutes=30),
    timedelta(hours=4, seconds=5),
]


def format_hms(duration: timedelta) -> str:
    """Format a timedelta as HH:MM:SS (hours may exceed 24)."""
    total_seconds = int(duration.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"


def total_duration(sessions: list[timedelta]) -> timedelta:
    """Return the sum of all session durations."""
    return sum(sessions, timedelta(0))


def main() -> None:
    total = total_duration(WORK_SESSIONS)
    print(format_hms(total))


if __name__ == "__main__":
    main()
