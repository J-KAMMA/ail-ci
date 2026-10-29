# task: Parse an embedded CSV and print the number of distinct values in each column.
from __future__ import annotations

import csv
import io

EMBEDDED_CSV: str = """\
name,city,department,salary,active
Alice,Berlin,Engineering,85000,yes
Bob,Paris,Marketing,62000,no
Carol,Berlin,Engineering,91000,yes
Dan,London,Sales,58000,yes
Eve,Paris,Engineering,85000,no
Frank,London,Marketing,62000,yes
Grace,Berlin,Sales,58000,yes
Heidi,Paris,Sales,,no
Ivan,London,Engineering,91000,yes
Judy,Berlin,Marketing,62000,
"""


def count_distinct_per_column(text: str) -> tuple[list[str], list[int]]:
    """Return the header names and the number of distinct values in each column."""
    reader = csv.reader(io.StringIO(text))
    header: list[str] = next(reader)
    distinct: list[set[str]] = [set() for _ in header]

    for row in reader:
        if not row:
            continue
        for index in range(len(header)):
            value = row[index] if index < len(row) else ""
            distinct[index].add(value)

    return header, [len(values) for values in distinct]


def main() -> None:
    header, counts = count_distinct_per_column(EMBEDDED_CSV)
    width = max(len(name) for name in header)
    for name, count in zip(header, counts):
        print(f"{name.ljust(width)} : {count}")


if __name__ == "__main__":
    main()
