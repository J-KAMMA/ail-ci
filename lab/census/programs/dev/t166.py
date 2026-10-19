import csv
import sys
from collections import defaultdict
from decimal import Decimal


def main() -> None:
    reader = csv.DictReader(sys.stdin)

    counts: dict[str, int] = defaultdict(int)
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal(0))

    for row in reader:
        dept = (row.get("dept") or "").strip()
        salary_text = (row.get("salary") or "0").strip()
        counts[dept] += 1
        totals[dept] += Decimal(salary_text)

    headers = ("dept", "count", "total")
    rows: list[tuple[str, str, str]] = []
    for dept in sorted(counts):
        rows.append((dept, str(counts[dept]), str(totals[dept])))

    widths = [
        max([len(headers[0])] + [len(r[0]) for r in rows]),
        max([len(headers[1])] + [len(r[1]) for r in rows]),
        max([len(headers[2])] + [len(r[2]) for r in rows]),
    ]

    def fmt(cells: tuple[str, str, str]) -> str:
        return "  ".join(
            [
                cells[0].ljust(widths[0]),
                cells[1].rjust(widths[1]),
                cells[2].rjust(widths[2]),
            ]
        )

    lines = [fmt(headers)] + [fmt(r) for r in rows]
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
