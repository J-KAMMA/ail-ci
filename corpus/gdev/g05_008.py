# task: Group a fixed list of (name, department) tuples into a dictionary mapping each department to its sorted names.
from collections import defaultdict
from typing import Dict, List, Tuple


EMPLOYEES: List[Tuple[str, str]] = [
    ("Alice", "Engineering"),
    ("Bob", "Marketing"),
    ("Charlie", "Engineering"),
    ("Diana", "Sales"),
    ("Eve", "Marketing"),
    ("Frank", "Engineering"),
    ("Grace", "Sales"),
    ("Heidi", "Human Resources"),
    ("Ivan", "Sales"),
    ("Judy", "Human Resources"),
    ("Mallory", "Engineering"),
    ("Niaj", "Marketing"),
]


def group_by_department(records: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    groups: defaultdict[str, List[str]] = defaultdict(list)
    for name, department in records:
        groups[department].append(name)
    return {dept: sorted(names) for dept, names in sorted(groups.items())}


def main() -> None:
    grouped = group_by_department(EMPLOYEES)
    for department, names in grouped.items():
        print(f"{department}: {', '.join(names)}")


if __name__ == "__main__":
    main()
