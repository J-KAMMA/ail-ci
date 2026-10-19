import sys


def parse_integer(text: str) -> int | None:
    """Return the integer value of text, or None if it is not an integer."""
    try:
        return int(text)
    except ValueError:
        return None


def main() -> None:
    total: int = 0
    for line_number, raw in enumerate(sys.stdin, start=1):
        text = raw.strip()
        if not text:
            # Empty lines carry no value and are skipped silently.
            continue
        value = parse_integer(text)
        if value is None:
            print(f"line {line_number}: invalid integer: {text!r}", file=sys.stderr)
            continue
        total += value
    print(total)
    sys.exit(0)


if __name__ == "__main__":
    main()
