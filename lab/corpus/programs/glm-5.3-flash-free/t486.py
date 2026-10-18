import sys
from datetime import datetime, timedelta


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        t = datetime.strptime(line, "%H:%M")
        new_t = t + timedelta(minutes=90)
        day_offset = (new_t.date() - t.date()).days
        print(f"{new_t.strftime('%H:%M')} +{day_offset}")


if __name__ == "__main__":
    main()
