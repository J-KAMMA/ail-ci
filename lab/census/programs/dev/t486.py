import sys
from datetime import date, datetime, timedelta


def main() -> None:
    base_date: date = date(2000, 1, 1)
    shift: timedelta = timedelta(minutes=90)

    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        parsed = datetime.strptime(text, "%H:%M")
        start = datetime.combine(base_date, parsed.time())
        end = start + shift
        offset = (end.date() - base_date).days
        print(f"{end:%H:%M} +{offset}")


if __name__ == "__main__":
    main()
