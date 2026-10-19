import calendar
import datetime
import sys


def main() -> None:
    weekend_count: int = 0
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        parts = line.split("-")
        if len(parts) != 3:
            continue
        try:
            year, month, day = (int(p) for p in parts)
        except ValueError:
            continue
        if not (1 <= month <= 12):
            continue
        # Leap-year aware day validation via calendar.
        _, days_in_month = calendar.monthrange(year, month)
        if not (1 <= day <= days_in_month):
            continue
        d = datetime.date(year, month, day)
        print(d.strftime("%A"))
        if d.weekday() >= 5:  # Saturday (5) or Sunday (6)
            weekend_count += 1
    print(f"weekend: {weekend_count}")


if __name__ == "__main__":
    main()
