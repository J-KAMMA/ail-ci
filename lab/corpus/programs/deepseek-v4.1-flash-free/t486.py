import sys
from datetime import datetime, timedelta


def main() -> None:
    base = datetime(2000, 1, 1)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        t = datetime.strptime(line, "%H:%M")
        shifted = t + timedelta(minutes=90)
        offset = (shifted.date() - t.date()).days
        print(f"{shifted.strftime('%H:%M')} +{offset}")


if __name__ == "__main__":
    main()
