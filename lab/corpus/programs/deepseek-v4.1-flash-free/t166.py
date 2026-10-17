import csv
import sys
from collections import defaultdict
from typing import Dict


def main() -> None:
    reader = csv.DictReader(sys.stdin)

    counts: Dict[str, int] = defaultdict(int)
    totals: Dict[str, int] = defaultdict(int)

    for row in reader:
        dept: str = row["dept"]
        salary: int = int(row["salary"])
        counts[dept] += 1
        totals[dept] += salary

    depts = sorted(totals)

    dept_w = max([len("dept")] + [len(d) for d in depts])
    count_w = max([len("count")] + [len(str(counts[d])) for d in depts])
    total_w = max([len("total")] + [len(str(totals[d])) for d in depts])

    print(f"{'dept':<{dept_w}} {'count':>{count_w}} {'total':>{total_w}}")
    for d in depts:
        print(f"{d:<{dept_w}} {counts[d]:>{count_w}} {totals[d]:>{total_w}}")


if __name__ == "__main__":
    main()
