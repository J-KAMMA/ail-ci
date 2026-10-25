# task: Parse embedded log lines with ISO 8601 timestamps and compute the elapsed seconds between the first and last entries.
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

LOG_TEXT = """\
2024-03-10T08:15:00Z INFO service started
2024-03-10T08:15:02.250Z DEBUG loading configuration
2024-03-10T09:00:00+01:00 WARN cache is 80% full
not-a-timestamp ERROR this line is malformed
2024-03-10T08:16:30.500+00:00 INFO request handled path=/api/items
2024-03-10T10:20:45.125+02:00 ERROR upstream timeout after 30s

2024-03-10T08:17:10Z INFO service heartbeat
"""

LINE_RE = re.compile(r"^(?P<ts>\S+)\s+(?P<level>[A-Z]+)\s+(?P<msg>.*)$")


@dataclass(frozen=True)
class Entry:
    timestamp: datetime
    level: str
    message: str


def parse_line(line: str) -> Entry | None:
    """Parse one log line; return None if it is blank or malformed."""
    stripped = line.strip()
    if not stripped:
        return None
    match = LINE_RE.match(stripped)
    if match is None:
        return None
    try:
        timestamp = datetime.fromisoformat(match["ts"])
    except ValueError:
        return None
    return Entry(timestamp=timestamp, level=match["level"], message=match["msg"])


def parse_log(text: str) -> tuple[list[Entry], int]:
    """Return (valid entries in file order, count of skipped non-blank lines)."""
    entries: list[Entry] = []
    skipped = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        entry = parse_line(line)
        if entry is None:
            skipped += 1
        else:
            entries.append(entry)
    return entries, skipped


def elapsed_seconds(entries: list[Entry]) -> float:
    """Seconds between the first and last entries (0.0 if fewer than two)."""
    if len(entries) < 2:
        return 0.0
    delta = entries[-1].timestamp - entries[0].timestamp
    return delta.total_seconds()


def main() -> None:
    entries, skipped = parse_log(LOG_TEXT)
    print(f"Parsed entries: {len(entries)}")
    print(f"Skipped lines: {skipped}")

    if not entries:
        print("No valid entries found.")
        return

    first, last = entries[0], entries[-1]
    print(f"First entry: {first.timestamp.isoformat()} [{first.level}] {first.message}")
    print(f"Last entry:  {last.timestamp.isoformat()} [{last.level}] {last.message}")
    print(f"Elapsed seconds: {elapsed_seconds(entries):.3f}")


if __name__ == "__main__":
    main()
