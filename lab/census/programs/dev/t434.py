import csv
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass(order=True)
class Employee:
    name: str
    dept: str = "unknown"
    salary: int = 0
    age: int = 0

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.dept = self.dept.strip()
        if not self.name:
            raise ValueError("name must be non-empty")
        if not self.dept:
            raise ValueError("dept must be non-empty")
        if self.salary < 0:
            raise ValueError(f"salary must be non-negative: {self.salary}")
        if self.age < 0:
            raise ValueError(f"age must be non-negative: {self.age}")


def _optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def read_employees(text: str) -> list[Employee]:
    reader = csv.DictReader(text.splitlines())
    employees: list[Employee] = []
    for row in reader:
        name = _optional(row.get("name"))
        if name is None:
            raise ValueError("missing name")
        kwargs: dict[str, object] = {"name": name}
        dept = _optional(row.get("dept"))
        if dept is not None:
            kwargs["dept"] = dept
        salary = _optional(row.get("salary"))
        if salary is not None:
            kwargs["salary"] = int(float(salary))
        age = _optional(row.get("age"))
        if age is not None:
            kwargs["age"] = int(age)
        employees.append(Employee(**kwargs))  # type: ignore[arg-type]
    return employees


def main() -> None:
    text = sys.stdin.read()
    employees = read_employees(text)
    for employee in sorted(employees)[:5]:
        print(employee)


if __name__ == "__main__":
    main()
