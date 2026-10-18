import csv
import sys
from collections import defaultdict


def main() -> None:
    reader = csv.DictReader(sys.stdin)
    names: set[str] = set()
    order: list[str] = []
    depts_by_name: dict[str, set[str]] = defaultdict(set)

    for row in reader:
        name = row["name"]
        dept = row["dept"]
        if name not in names:
            names.add(name)
            order.append(name)
        depts_by_name[name].add(dept)

    print(len(names))
    for name in order:
        if len(depts_by_name[name]) >= 2:
            print(name)


if __name__ == "__main__":
    main()
