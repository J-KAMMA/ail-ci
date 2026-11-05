# task: Determine the ISO week number and ISO year for every Sunday in 2024 and print them.
from datetime import date, timedelta


def main() -> None:
    # Python's date.weekday(): Monday == 0 ... Sunday == 6.
    # Advance from January 1, 2024 to the first Sunday of the year.
    current: date = date(2024, 1, 1)
    current += timedelta(days=(6 - current.weekday()) % 7)

    while current.year == 2024:
        iso = current.isocalendar()
        print(
            f"{current.isoformat()} (Sunday): "
            f"ISO year {iso.year}, ISO week {iso.week:02d}"
        )
        current += timedelta(days=7)


if __name__ == "__main__":
    main()
