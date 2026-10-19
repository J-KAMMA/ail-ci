import re
import sys

LINE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(INFO|WARN|ERROR|DEBUG)\]"
)

SEVERITY_RANK: dict[str, int] = {
    "ERROR": 0,
    "WARN": 1,
    "INFO": 2,
    "DEBUG": 3,
}


def parse_line(line: str) -> tuple[int, str, str] | None:
    """Return (severity rank, timestamp, original line) or None if malformed."""
    match = LINE_PATTERN.match(line)
    if match is None:
        return None
    timestamp, level = match.group(1), match.group(2)
    return SEVERITY_RANK[level], timestamp, line


def main() -> None:
    records: list[tuple[int, str, str]] = []
    for raw in sys.stdin:
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        parsed = parse_line(line)
        if parsed is not None:
            records.append(parsed)

    # Sort by severity (ERROR first), then by timestamp ascending.
    # Python's sort is stable, so ties keep their input order.
    records.sort(key=lambda rec: (rec[0], rec[1]))

    for _, _, line in records[:8]:
        print(line)


if __name__ == "__main__":
    main()
