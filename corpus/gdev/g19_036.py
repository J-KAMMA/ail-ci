# task: Calculate the time remaining until a fixed launch time 2030-01-01 00:00 UTC from a fixed reference datetime and print it as a timedelta.
from datetime import datetime, timedelta, timezone

LAUNCH_TIME: datetime = datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
REFERENCE_TIME: datetime = datetime(2025, 6, 15, 12, 30, 0, tzinfo=timezone.utc)


def time_until_launch(reference: datetime, launch: datetime) -> timedelta:
    return launch - reference


def main() -> None:
    remaining: timedelta = time_until_launch(REFERENCE_TIME, LAUNCH_TIME)
    print(remaining)


if __name__ == "__main__":
    main()
