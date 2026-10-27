# task: Parse an embedded CSV and count the rows whose text column matches a given regular expression pattern.
import csv
import io
import re
from collections.abc import Iterable

EMBEDDED_CSV: str = """id,name,text
1,alpha,"The quick brown fox"
2,beta,"Lazy dog, sleeping"
3,gamma,"Error: disk full"
4,delta,"multi
line text with error"
5,epsilon,"ERROR code 42"
6,zeta,"nothing here"
7,eta,"error_404 found"
8,theta,"Errors are rare"
"""

PATTERN: str = r"\berror\b"


def iter_rows(text: str) -> Iterable[dict[str, str]]:
    """Yield each CSV row as a dictionary keyed by the header names."""
    reader = csv.DictReader(io.StringIO(text, newline=""))
    yield from reader


def find_matching_ids(
    rows: Iterable[dict[str, str]],
    pattern: re.Pattern[str],
) -> list[str]:
    """Return the ids of rows whose text column matches the pattern."""
    matched: list[str] = []
    for row in rows:
        value: str = row.get("text") or ""
        if pattern.search(value) is not None:
            matched.append(row.get("id") or "")
    return matched


def main() -> None:
    compiled: re.Pattern[str] = re.compile(PATTERN, re.IGNORECASE)
    rows: list[dict[str, str]] = list(iter_rows(EMBEDDED_CSV))
    matched_ids: list[str] = find_matching_ids(rows, compiled)

    print(f"Pattern: {PATTERN!r} (case-insensitive)")
    print(f"Total rows: {len(rows)}")
    print(f"Matching rows: {len(matched_ids)}")
    print(f"Matching ids: {', '.join(matched_ids)}")


if __name__ == "__main__":
    main()
