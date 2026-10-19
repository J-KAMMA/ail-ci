import csv
import sys
from fractions import Fraction


def decade_label(age: int) -> str:
    return f"{(age // 10) * 10}s"


def round_half_up(value: Fraction) -> int:
    """Round a non-negative Fraction to the nearest integer, halves rounding up."""
    return int((value + Fraction(1, 2)).__floor__())


def main() -> None:
    reader = csv.DictReader(sys.stdin)
    buckets: dict[int, list[Fraction]] = {}

    for row in reader:
        try:
            salary = Fraction(row["salary"].strip())
            age = int(Fraction(row["age"].strip()))
        except (KeyError, ValueError, ZeroDivisionError, AttributeError, TypeError):
            continue
        decade = (age // 10) * 10
        buckets.setdefault(decade, []).append(salary)

    for decade in sorted(buckets):
        salaries = buckets[decade]
        count = len(salaries)
        mean = sum(salaries, Fraction(0)) / count
        print(f"{decade}s: count={count} mean_salary={round_half_up(mean)}")


if __name__ == "__main__":
    main()
