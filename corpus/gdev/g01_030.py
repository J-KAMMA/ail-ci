# task: Parse embedded key=value lines and classify each value as an integer, float, boolean, or string, then print the classification.
import re
from collections import Counter
from typing import Final, NamedTuple


SAMPLE_DATA: Final[str] = """
# Embedded configuration sample
server_port = 8080
timeout = 2.5
debug = True
verbose = false
retries = -3
ratio = .75
scientific = 6.02e23
label = production
empty =
version = 1.2.3
negative_float = -0.001
flag_upper = FALSE
count = +42
mixed = 12abc
"""

INT_PATTERN: Final[re.Pattern[str]] = re.compile(r"[+-]?[0-9]+")
FLOAT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[+-]?(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?"
)
BOOLEAN_WORDS: Final[frozenset[str]] = frozenset({"true", "false"})


class Entry(NamedTuple):
    key: str
    value: str


def parse_lines(text: str) -> list[Entry]:
    """Parse key=value lines, skipping blanks and comments, preserving order."""
    entries: list[Entry] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        entries.append(Entry(key.strip(), value.strip()))
    return entries


def classify(value: str) -> str:
    """Return one of: 'boolean', 'integer', 'float', 'string'."""
    if value.lower() in BOOLEAN_WORDS:
        return "boolean"
    if INT_PATTERN.fullmatch(value):
        return "integer"
    if FLOAT_PATTERN.fullmatch(value):
        return "float"
    return "string"


def main() -> None:
    entries: list[Entry] = parse_lines(SAMPLE_DATA)
    counts: Counter[str] = Counter()

    print("Classification results:")
    for entry in entries:
        kind: str = classify(entry.value)
        counts[kind] += 1
        print(f"  {entry.key:<16} -> {kind:<8} (value={entry.value!r})")

    print()
    print("Summary:")
    for kind in sorted(counts):
        print(f"  {kind}: {counts[kind]}")


if __name__ == "__main__":
    main()
