from datetime import date, timedelta


def main() -> None:
    start = date(2023, 12, 25)
    for i in range(12):
        day = start + timedelta(days=i)
        iso = day.isocalendar()
        print(day.isoformat(), day.strftime("%a %G-W%V-%u"), iso.year, iso.week, iso.weekday)
    for text in ["2024-01-01", "2021-01-01", "2026-12-31"]:
        day = date.fromisoformat(text)
        print(text, day.isocalendar(), day.strftime("%G %V %u"))
    print(date.fromisocalendar(2024, 1, 1).isoformat())
    print(date.fromisocalendar(2020, 53, 7).isoformat())


main()
