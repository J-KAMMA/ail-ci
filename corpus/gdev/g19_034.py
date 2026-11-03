# task: Generate a schedule of the first seven days starting from 2024-12-29 with their weekday names and ISO dates.
from datetime import date, timedelta


def main() -> None:
    start: date = date(2024, 12, 29)
    for offset in range(7):
        current: date = start + timedelta(days=offset)
        print(f"{current.strftime('%A')} {current.isoformat()}")


if __name__ == "__main__":
    main()
