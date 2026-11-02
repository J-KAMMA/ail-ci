# task: Parse embedded CSV rows and print them sorted by one text column ascending and a second numeric column descending.
import csv
import io
from typing import List, Dict


EMBEDDED_CSV = """name,department,salary,years
Alice,Engineering,95000,6
Bob,Marketing,72000,4
Carol,Engineering,105000,9
Dave,Sales,68000,2
Eve,Marketing,81000,7
Frank,Engineering,95000,3
Grace,Sales,74000,5
Heidi,Marketing,81000,1
Ivan,Sales,68000,8
Judy,Engineering,120000,10
"""


def parse_rows(text: str) -> List[Dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def sort_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    # Ascending by department (text), then descending by salary (numeric).
    # Ties are broken by name ascending to keep output fully deterministic.
    return sorted(
        rows,
        key=lambda r: (r["department"], -int(r["salary"]), r["name"]),
    )


def format_row(row: Dict[str, str]) -> str:
    return (
        f"{row['department']:<12} {row['name']:<8} "
        f"{int(row['salary']):>8} {int(row['years']):>3}"
    )


def main() -> None:
    rows = parse_rows(EMBEDDED_CSV)
    sorted_rows = sort_rows(rows)

    print(f"{'department':<12} {'name':<8} {'salary':>8} {'years':>3}")
    print("-" * 34)
    for row in sorted_rows:
        print(format_row(row))


if __name__ == "__main__":
    main()
