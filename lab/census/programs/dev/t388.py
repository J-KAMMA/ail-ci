import sys
from datetime import date

WEEKDAY_ABBR: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def main() -> None:
    dates: list[date] = []
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        dates.append(date.fromisoformat(text))

    dates.sort(key=lambda d: (d.weekday(), d.day))

    for d in dates[:8]:
        print(f"{d.isoformat()} {WEEKDAY_ABBR[d.weekday()]}")


if __name__ == "__main__":
    main()
