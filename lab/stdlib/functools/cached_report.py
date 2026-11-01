"""A report whose total is computed once with functools.cached_property."""
from functools import cached_property


class Report:
    def __init__(self, name, rows):
        self.name = name
        self.rows = rows
        self.calls = 0

    @cached_property
    def total(self):
        self.calls += 1
        return sum(self.rows)

    @cached_property
    def average(self):
        return self.total / len(self.rows) if self.rows else 0


def main() -> None:
    report = Report("daily", [3, 8, 12, 5])
    print(report.name, report.total, report.calls)
    print(report.total, report.calls)
    print(report.average, report.total, report.calls)
    del report.total
    print(report.total, report.calls)
    empty = Report("empty", [])
    print(empty.total, empty.average)
    print("total" in report.__dict__, "average" in report.__dict__)


main()
