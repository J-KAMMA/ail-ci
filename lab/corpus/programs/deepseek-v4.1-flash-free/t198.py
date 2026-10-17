import calendar
import sys
from datetime import date


def is_valid(y: int, m: int, d: int) -> bool:
    if not 1 <= m <= 12:
        return False
    return 1 <= d <= calendar.monthrange(y, m)[1]


def main() -> None:
    weekend_count = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        y, m, d = map(int, line.split("-"))
        if not is_valid(y, m, d):
            continue
        current = date(y, m, d)
        print(current.strftime("%A"))
        if current.weekday() >= 5:
            weekend_count += 1
    print(weekend_count)


if __name__ == "__main__":
    main()
