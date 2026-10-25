# task: Compute the average grade per class from fixed records by sorting with a key and aggregating with itertools.groupby.
from itertools import groupby
from typing import NamedTuple


class Record(NamedTuple):
    student: str
    class_name: str
    grade: float


RECORDS: list[Record] = [
    Record("Alice", "Math", 91.5),
    Record("Bob", "Science", 78.0),
    Record("Carol", "Math", 84.5),
    Record("Dave", "History", 88.0),
    Record("Eve", "Science", 95.0),
    Record("Frank", "Math", 67.0),
    Record("Grace", "History", 72.5),
    Record("Heidi", "Science", 81.0),
    Record("Ivan", "History", 90.0),
    Record("Judy", "Math", 79.5),
    Record("Mallory", "Science", 69.0),
    Record("Niaj", "History", 85.5),
]


def average_by_class(records: list[Record]) -> list[tuple[str, float, int]]:
    """Return (class_name, average_grade, count) sorted by class name."""
    ordered = sorted(records, key=lambda r: r.class_name)
    results: list[tuple[str, float, int]] = []
    for class_name, group in groupby(ordered, key=lambda r: r.class_name):
        grades = [r.grade for r in group]
        average = sum(grades) / len(grades)
        results.append((class_name, average, len(grades)))
    return results


def main() -> None:
    print(f"{'Class':<12}{'Average':>10}{'Students':>10}")
    print("-" * 32)
    for class_name, average, count in average_by_class(RECORDS):
        print(f"{class_name:<12}{average:>10.2f}{count:>10}")


if __name__ == "__main__":
    main()
