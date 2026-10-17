import csv
import sys
from collections import defaultdict


def fmt_row(cells: tuple[str, str, str], widths: tuple[int, int, int],
            aligns: tuple[str, str, str]) -> str:
    parts = []
    for cell, width, align in zip(cells, widths, aligns):
        parts.append(cell.rjust(width) if align == ">" else cell.ljust(width))
    return "  ".join(parts)


def main() -> None:
    counts: dict[str, int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)
    for row in csv.DictReader(sys.stdin):
        dept = row["dept"]
        counts[dept] += 1
        totals[dept] += int(row["salary"])

    depts = list(counts)
    dept_width = max([len("dept")] + [len(d) for d in depts])
    count_width = max([len("count")] + [len(str(c)) for c in counts.values()])
    total_width = max([len("total")] + [len(str(t)) for t in totals.values()])
    widths = (dept_width, count_width, total_width)
    aligns = ("<", ">", ">")

    print(fmt_row(("dept", "count", "total"), widths, aligns))
    for dept in depts:
        print(fmt_row((dept, str(counts[dept]), str(totals[dept])), widths, aligns))


if __name__ == "__main__":
    main()
