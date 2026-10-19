import csv
import sys


def main() -> None:
    reader = csv.reader(sys.stdin)
    header = next(reader, None)
    if header is None:
        print(0)
        return

    columns = [h.strip() for h in header]
    name_idx = columns.index("name") if "name" in columns else 0
    dept_idx = columns.index("dept") if "dept" in columns else 1

    depts_by_name: dict[str, set[str]] = {}
    for row in reader:
        if not row or len(row) <= max(name_idx, dept_idx):
            continue
        name = row[name_idx].strip()
        dept = row[dept_idx].strip()
        depts_by_name.setdefault(name, set()).add(dept)

    print(len(depts_by_name))
    for name in sorted(n for n, depts in depts_by_name.items() if len(depts) >= 2):
        print(name)


if __name__ == "__main__":
    main()
