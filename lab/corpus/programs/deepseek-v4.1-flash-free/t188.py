import sys
from collections import Counter


def parse_line(line: str) -> tuple[str, str, str] | None:
    """Return (time, level, code) for a valid log line, else None."""
    parts = line.split()
    if len(parts) < 4 or not parts[2].startswith("["):
        return None

    time = parts[1]
    level = parts[2].strip("[]")

    code = ""
    for token in parts[3:]:
        if token.startswith("code="):
            code = token[len("code="):]
            break

    return time, level, code


def main() -> None:
    counts: Counter[str] = Counter()

    for line in sys.stdin:
        parsed = parse_line(line.strip())
        if parsed is None:
            continue

        time, level, code = parsed
        counts[level] += 1

        if level == "ERROR":
            print(f"{time} {code}")

    for level in sorted(counts):
        print(f"{level} {counts[level]}")


if __name__ == "__main__":
    main()
