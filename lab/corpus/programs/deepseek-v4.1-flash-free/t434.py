import sys
import csv
from dataclasses import dataclass, field


@dataclass(order=True)
class Employee:
    name: str
    dept: str
    salary: float = 0.0
    age: int = 0
    tags: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")
        if not self.dept:
            raise ValueError("dept must not be empty")
        if self.salary < 0:
            raise ValueError("salary must not be negative")
        if not 0 <= self.age <= 150:
            raise ValueError("age out of range")


def main() -> None:
    reader = csv.DictReader(sys.stdin)
    employees = [
        Employee(
            name=row["name"],
            dept=row["dept"],
            salary=float(row["salary"]),
            age=int(row["age"]),
        )
        for row in reader
    ]
    for emp in sorted(employees)[:5]:
        print(f"{emp.name} {emp.dept} {emp.salary} {emp.age}")


if __name__ == "__main__":
    main()
