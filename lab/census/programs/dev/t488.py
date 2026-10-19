import sys


def parse_duration(text: str) -> int:
    """Convert an 'HH:MM' string into a total number of minutes."""
    hours_part, minutes_part = text.strip().split(":")
    return int(hours_part) * 60 + int(minutes_part)


def main() -> None:
    total_minutes: int = 0
    for line in sys.stdin:
        stripped = line.strip()
        if not stripped:
            continue
        total_minutes += parse_duration(stripped)

    hours, minutes = divmod(total_minutes, 60)
    print(f"{hours}:{minutes:02d}")


if __name__ == "__main__":
    main()
