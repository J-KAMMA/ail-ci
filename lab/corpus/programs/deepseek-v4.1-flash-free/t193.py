import sys
from collections import defaultdict
from datetime import datetime
from statistics import mean

LEVELS = ("INFO", "WARN", "ERROR", "DEBUG")


def parse_line(line: str) -> tuple[datetime, str, int] | None:
    parts = line.rsplit(" ", 1)
    if len(parts) != 2:
        return None
    head, code_field = parts
    if not code_field.startswith("code="):
        return None
    try:
        code = int(code_field[5:])
    except ValueError:
        return None
    ts_field, _, rest = head.partition(" ")
    level_field, _, _ = rest.partition(" ")
    if level_field.startswith("[") and level_field.endswith("]"):
        level = level_field[1:-1]
    else:
        return None
    try:
        ts = datetime.strptime(ts_field, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return ts, level, code


def main() -> None:
    entries: list[tuple[datetime, str, int]] = []
    for raw in sys.stdin:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        parsed = parse_line(line)
        if parsed is not None:
            entries.append(parsed)

    entries.sort(key=lambda e: e[0])

    for ts, level, code in entries[:5]:
        print(f"{ts:%Y-%m-%d %H:%M:%S} [{level}] code={code}")

    by_level: dict[str, list[int]] = defaultdict(list)
    for _, level, code in entries:
        by_level[level].append(code)

    for level in LEVELS:
        if level in by_level:
            avg = round(mean(by_level[level]), 1)
            print(f"{level} avg={avg:.1f}")


if __name__ == "__main__":
    main()
