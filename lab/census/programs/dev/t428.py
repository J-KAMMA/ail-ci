import sys


def lookup(table: dict[str, int], key: str) -> str:
    """Return the count for key as text, or 'missing' if the key is absent."""
    try:
        return str(table[key])
    except KeyError:
        return "missing"


def main() -> None:
    lines: list[str] = sys.stdin.read().splitlines()

    counts: dict[str, int] = {}
    positions: dict[str, list[int]] = {}

    for index, raw in enumerate(lines):
        token = raw.strip()
        if not token:
            continue
        counts[token] = counts.get(token, 0) + 1
        positions.setdefault(token, []).append(index)

    for key in ("5", "0", "-3", "2"):
        print(lookup(counts, key))


if __name__ == "__main__":
    main()
