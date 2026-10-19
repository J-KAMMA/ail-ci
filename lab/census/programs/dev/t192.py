import sys
from collections import Counter


def main() -> None:
    month_counts: Counter[str] = Counter()
    first_warn: str | None = None

    for raw in sys.stdin:
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        parts = line.split()
        if not parts:
            continue

        date_str = parts[0]
        month = date_str[:7]
        month_counts[month] += 1

        if first_warn is None and len(parts) > 2 and parts[2] == "[WARN]":
            first_warn = line

    for month in sorted(month_counts):
        print(f"{month}: {month_counts[month]}")

    if first_warn is None:
        print("first WARN: none")
    else:
        print(f"first WARN: {first_warn}")


if __name__ == "__main__":
    main()
