import csv
import sys
from collections import defaultdict


def median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def fmt(x: float) -> str:
    return str(int(x)) if x.is_integer() else repr(x)


def main() -> None:
    reader = csv.DictReader(sys.stdin)
    groups: dict[str, list[float]] = defaultdict(list)
    for row in reader:
        groups[row["dept"]].append(float(row["salary"]))

    for dept in sorted(groups):
        salaries = groups[dept]
        lo = min(salaries)
        hi = max(salaries)
        print(f"{dept}: {fmt(lo)}-{fmt(hi)} {median(salaries)}")


if __name__ == "__main__":
    main()
