import csv
import sys
from collections import defaultdict


def main() -> None:
    reader = csv.DictReader(sys.stdin)
    buckets: dict[int, list[float]] = defaultdict(list)

    for row in reader:
        age = int(row["age"])
        salary = float(row["salary"])
        decade = (age // 10) * 10
        buckets[decade].append(salary)

    for decade in sorted(buckets):
        salaries = buckets[decade]
        mean = round(sum(salaries) / len(salaries))
        print(f"{decade}s {len(salaries)} {mean}")


if __name__ == "__main__":
    main()
