# task: Use a namedtuple to represent hardcoded student records and compute the average grade per class using a defaultdict.
from collections import defaultdict
from typing import NamedTuple


class Student(NamedTuple):
    name: str
    student_id: int
    class_name: str
    grade: float


STUDENTS: list[Student] = [
    Student("Alice Johnson", 1001, "Math", 92.5),
    Student("Bob Smith", 1002, "Math", 78.0),
    Student("Carol White", 1003, "Science", 85.5),
    Student("David Brown", 1004, "Science", 91.0),
    Student("Eve Davis", 1005, "History", 88.0),
    Student("Frank Miller", 1006, "Math", 69.5),
    Student("Grace Wilson", 1007, "History", 94.0),
    Student("Henry Moore", 1008, "Science", 73.5),
    Student("Ivy Taylor", 1009, "History", 81.0),
    Student("Jack Anderson", 1010, "Math", 86.0),
]


def compute_average_by_class(students: list[Student]) -> dict[str, float]:
    totals: defaultdict[str, float] = defaultdict(float)
    counts: defaultdict[str, int] = defaultdict(int)

    for student in students:
        totals[student.class_name] += student.grade
        counts[student.class_name] += 1

    return {
        class_name: totals[class_name] / counts[class_name]
        for class_name in sorted(totals)
    }


def main() -> None:
    averages = compute_average_by_class(STUDENTS)

    print("Average grade per class:")
    for class_name, average in averages.items():
        print(f"  {class_name}: {average:.2f}")


if __name__ == "__main__":
    main()
