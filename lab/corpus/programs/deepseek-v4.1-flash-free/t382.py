import re
import sys

SEVERITY_ORDER = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}

LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"\[(?P<level>INFO|WARN|ERROR|DEBUG)\]"
)


def sort_key(index: int, line: str) -> tuple[int, str, int]:
    match = LINE_PATTERN.match(line)
    if match is None:
        raise ValueError(f"unrecognized log line: {line!r}")
    severity = SEVERITY_ORDER[match.group("level")]
    timestamp = match.group("timestamp")
    return (-severity, timestamp, index)


def main() -> None:
    lines = [line.rstrip("\n") for line in sys.stdin if line.strip()]

    ordered = sorted(enumerate(lines), key=lambda pair: sort_key(pair[0], pair[1]))

    for _, line in ordered[:8]:
        print(line)


if __name__ == "__main__":
    main()
