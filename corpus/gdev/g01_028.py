# task: Parse embedded log lines and rebuild multi-line stack traces by joining continuation lines that begin with whitespace, then print the trace count.
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

LOG_TEXT = """\
2024-05-01 10:00:00 INFO Service starting
2024-05-01 10:00:01 INFO Loading configuration
2024-05-01 10:00:02 ERROR Request failed
    Traceback (most recent call last):
      File "app/server.py", line 42, in handle
        result = process(request)
      File "app/worker.py", line 17, in process
        return 1 / 0
    ZeroDivisionError: division by zero
2024-05-01 10:00:03 WARN Retrying job 17
2024-05-01 10:00:04 INFO Job 17 queued
2024-05-01 10:00:05 ERROR Database timeout
    Traceback (most recent call last):
      File "app/db.py", line 88, in query
        cursor.execute(sql)
    TimeoutError: query exceeded 30s
2024-05-01 10:00:06 INFO Heartbeat ok
  continuation without a traceback header
2024-05-01 10:00:07 ERROR Parse failure
    Traceback (most recent call last):
      File "app/parser.py", line 9, in parse
        return json.loads(text)
    ValueError: malformed input
2024-05-01 10:00:08 INFO Shutdown requested
"""

RECORD_START = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}) (?P<level>[A-Z]+) "
)
TRACE_HEADER = "Traceback (most recent call last):"


@dataclass
class LogRecord:
    """A logical log entry: a header line plus any continuation lines."""

    level: str
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def is_multiline(self) -> bool:
        return len(self.lines) > 1

    def is_trace(self) -> bool:
        return self.is_multiline and TRACE_HEADER in self.text


def parse_records(text: str) -> list[LogRecord]:
    """Join continuation lines (those starting with whitespace) to the prior record."""
    records: list[LogRecord] = []
    current: LogRecord | None = None

    for raw in text.splitlines():
        if not raw.strip():
            continue

        if raw[0].isspace():
            if current is None:
                # Continuation with no preceding header: ignore it.
                continue
            current.lines.append(raw.rstrip())
            continue

        match = RECORD_START.match(raw)
        level = match.group("level") if match else "UNKNOWN"
        current = LogRecord(level=level, lines=[raw.rstrip()])
        records.append(current)

    return records


def main() -> None:
    records = parse_records(LOG_TEXT)

    traces = [record for record in records if record.is_trace()]
    multiline = [record for record in records if record.is_multiline]
    levels = Counter(record.level for record in records)

    print(f"Total records: {len(records)}")
    print(f"Multi-line records: {len(multiline)}")
    print("Records by level:")
    for level in sorted(levels):
        print(f"  {level}: {levels[level]}")

    for index, trace in enumerate(traces, start=1):
        print(f"--- Stack trace {index} ({trace.level}, {len(trace.lines)} lines) ---")
        print(trace.text)

    print(f"Stack trace count: {len(traces)}")


if __name__ == "__main__":
    main()
