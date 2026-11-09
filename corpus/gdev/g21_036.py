# task: Serialize a Python object with a custom to_dict method using a default function passed to json.dumps and print the result.
import json
from datetime import date
from typing import Any


class Employee:
    def __init__(self, name: str, hired: date, skills: list[str], manager: "Employee | None" = None) -> None:
        self.name = name
        self.hired = hired
        self.skills = skills
        self.manager = manager

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "hired": self.hired,
            "skills": sorted(self.skills),
        }
        if self.manager is not None:
            result["manager"] = self.manager.name
        return result


def default_encoder(obj: Any) -> Any:
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def main() -> None:
    boss = Employee("Alice", date(2015, 3, 1), ["management", "python"])
    dev = Employee("Bob", date(2020, 7, 15), ["sql", "python", "go"], manager=boss)
    team = {"lead": boss, "members": [dev]}

    text = json.dumps(team, default=default_encoder, indent=2, sort_keys=True)
    print(text)


if __name__ == "__main__":
    main()
