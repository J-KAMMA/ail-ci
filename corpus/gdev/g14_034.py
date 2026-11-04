# task: Define a dataclass Student with a grades list and compute the average and letter grade for each student.
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Student:
    name: str
    grades: list[float] = field(default_factory=list)

    def average(self) -> float:
        if not self.grades:
            return 0.0
        return sum(self.grades) / len(self.grades)

    def letter_grade(self) -> str:
        avg = self.average()
        if avg >= 90:
            return "A"
        if avg >= 80:
            return "B"
        if avg >= 70:
            return "C"
        if avg >= 60:
            return "D"
        return "F"


def build_students() -> list[Student]:
    return [
        Student("Alice", [95.0, 88.5, 92.0, 79.0]),
        Student("Bob", [72.0, 65.5, 70.0, 68.0]),
        Student("Charlie", [55.0, 61.0, 58.5, 49.0]),
        Student("Diana", [88.0, 91.5, 85.0, 90.0]),
        Student("Eve", []),
    ]


def main() -> None:
    students = build_students()
    for student in students:
        avg = student.average()
        print(f"{student.name:<10} average={avg:6.2f} grade={student.letter_grade()}")

    best = max(students, key=lambda s: s.average())
    print(f"Top student: {best.name} ({best.average():.2f})")


if __name__ == "__main__":
    main()
