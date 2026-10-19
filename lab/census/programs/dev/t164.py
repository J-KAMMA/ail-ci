import csv
import sys
from collections import defaultdict


def main() -> None:
    reader = csv.DictReader(sys.stdin)
    totals: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)

    for row in reader:
        if not row:
            continue
        dept = (row.get("dept") or "").strip()
        salary_text = (row.get("salary") or "").strip()
        if not dept or not salary_text:
            continue
        try:
            salary = int(salary_text)
        except ValueError:
            salary = int(float(salary_text))
        totals[dept] += salary
        counts[dept] += 1

    for dept in sorted(totals):
        average = totals[dept] // counts[dept]
        print(f"{dept},{average}")


if __name__ == "__main__":
    main()
