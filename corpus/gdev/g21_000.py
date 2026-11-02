# task: Serialize a nested dictionary of student records to a JSON string with sorted keys and an indent of 4, then print it.
import json
from typing import Any


def build_student_records() -> dict[str, dict[str, Any]]:
    return {
        "student_003": {
            "name": "Charlie Brown",
            "age": 20,
            "major": "Mathematics",
            "courses": {
                "MATH201": {"title": "Linear Algebra", "grade": "B+", "credits": 4},
                "CS101": {"title": "Intro to Programming", "grade": "A-", "credits": 3},
            },
            "enrolled": True,
            "gpa": 3.4,
        },
        "student_001": {
            "name": "Alice Smith",
            "age": 19,
            "major": "Computer Science",
            "courses": {
                "CS101": {"title": "Intro to Programming", "grade": "A", "credits": 3},
                "ENG102": {"title": "Composition", "grade": "A-", "credits": 3},
            },
            "enrolled": True,
            "gpa": 3.9,
        },
        "student_002": {
            "name": "Bob Jones",
            "age": 21,
            "major": "Physics",
            "courses": {
                "PHY150": {"title": "Mechanics", "grade": "B", "credits": 4},
            },
            "enrolled": False,
            "gpa": 3.0,
            "notes": None,
        },
    }


def serialize_records(records: dict[str, Any]) -> str:
    return json.dumps(records, sort_keys=True, indent=4)


def main() -> None:
    records = build_student_records()
    print(serialize_records(records))


if __name__ == "__main__":
    main()
