from datetime import date, timedelta


def age_on(born: date, on: date) -> tuple:
    years = on.year - born.year
    months = on.month - born.month
    days = on.day - born.day
    if days < 0:
        months -= 1
        previous = on.replace(day=1) - timedelta(days=1)
        days += previous.day
    if months < 0:
        years -= 1
        months += 12
    return years, months, days


def report(name: str, born_text: str, on: date) -> None:
    try:
        born = date.fromisoformat(born_text)
    except ValueError as e:
        print(name, "invalid:", e)
        return
    years, months, days = age_on(born, on)
    print(name, born.strftime("%d %B %Y"), "age", years, months, days,
          "leap" if born.replace(year=2000).month == 2 and born.day == 29 else "")


def main() -> None:
    today = date(2024, 3, 1)
    report("Ada", "1989-12-10", today)
    report("Bob", "2000-02-29", today)
    report("Cy", "2024-02-29", today)
    report("Di", "1999-13-01", today)
    try:
        date(2023, 2, 29)
    except ValueError as e:
        print("bad day", type(e).__name__, e)
    print(date(2024, 2, 29) - date(2023, 2, 28))


main()
