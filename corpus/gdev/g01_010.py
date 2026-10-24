# task: Detect duplicate keys in an embedded key=value configuration and report each duplicate with its line number.
"""Detect duplicate keys in an embedded key=value configuration.

Each key is qualified by its most recent [section] header (if any), so the
same key name may appear in different sections without being a duplicate.
Duplicates are reported with the line number of their first definition and
the line numbers of every later redefinition. Output follows the order in
which keys first appear, so it is fully deterministic.
"""

from __future__ import annotations

EMBEDDED_CONFIG: str = """\
# application config
[server]
host = example.com
port = 8080
timeout = 30
port = 9090
[database]
url = postgres://localhost/app
pool = 5
url = postgres://localhost/other
bad line without equals
[server]
host=example.org
debug = true
debug = false
; comment with an equals sign = not a key
= value with empty key
"""


def parse_config(text: str) -> tuple[dict[str, list[int]], list[int]]:
    """Parse the configuration text.

    Returns a mapping from fully qualified key name to the list of line
    numbers where it appears (in file order), and a list of line numbers
    that could not be parsed as key=value pairs.
    """
    occurrences: dict[str, list[int]] = {}
    malformed: list[int] = []
    section = ""

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line[0] in "#;":
            continue

        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue

        key_part, separator, _ = line.partition("=")
        key = key_part.strip()
        if not separator or not key:
            malformed.append(lineno)
            continue

        full_key = f"{section}.{key}" if section else key
        occurrences.setdefault(full_key, []).append(lineno)

    return occurrences, malformed


def find_duplicates(occurrences: dict[str, list[int]]) -> dict[str, list[int]]:
    """Return only the keys that occur more than once, preserving order."""
    return {key: lines for key, lines in occurrences.items() if len(lines) > 1}


def format_report(duplicates: dict[str, list[int]], malformed: list[int]) -> str:
    """Build the human-readable report text."""
    out: list[str] = []

    if duplicates:
        out.append(f"Duplicate keys found: {len(duplicates)}")
        for key, lines in duplicates.items():
            first, *rest = lines
            later = ", ".join(str(n) for n in rest)
            out.append(
                f"  '{key}': first defined at line {first}, "
                f"duplicated at line(s) {later}"
            )
    else:
        out.append("No duplicate keys found.")

    if malformed:
        out.append("Malformed lines (no key=value pair):")
        for lineno in malformed:
            out.append(f"  line {lineno}")

    return "\n".join(out)


def main() -> None:
    occurrences, malformed = parse_config(EMBEDDED_CONFIG)
    duplicates = find_duplicates(occurrences)
    print(format_report(duplicates, malformed))


if __name__ == "__main__":
    main()
