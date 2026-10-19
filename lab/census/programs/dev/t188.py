import re
import sys
from collections import Counter

LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+\[([A-Za-z]+)\]\s+.*?code=(-?\d+)"
)


def main() -> None:
    level_counts: Counter[str] = Counter()
    error_lines: list[str] = []

    for raw in sys.stdin:
        line = raw.strip()
        match = LINE_RE.match(line)
        if not match:
            continue
        _date, time_str, level, code = match.groups()
        level_counts[level] += 1
        if level == "ERROR":
            error_lines.append(f"{time_str} {code}")

    for entry in error_lines:
        print(entry)
    for level in sorted(level_counts):
        print(f"{level} {level_counts[level]}")


if __name__ == "__main__":
    main()
