import csv
import sys


def main() -> None:
    reader = csv.reader(sys.stdin)
    header = next(reader, None)
    if header is None:
        return

    depts_by_name: dict[str, set[str]] = {}
    for row in reader:
        if not row:
            continue
        name, dept = row[0], row[1]
        depts_by_name.setdefault(name, set()).add(dept)

    print(len(depts_by_name))
    for name in sorted(n for n, d in depts_by_name.items() if len(d) >= 2):
        print(name)


if __name__ == "__main__":
    main()
