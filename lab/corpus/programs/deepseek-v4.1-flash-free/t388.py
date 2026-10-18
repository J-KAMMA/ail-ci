import sys
from datetime import date


def main() -> None:
    dates: list[date] = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            dates.append(date.fromisoformat(line))

    dates.sort(key=lambda d: (d.weekday(), d.day))

    abbrevs = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for d in dates[:8]:
        print(f"{abbrevs[d.weekday()]} {d.isoformat()}")


if __name__ == "__main__":
    main()
