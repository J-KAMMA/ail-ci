import sys
from enum import Enum, IntEnum


class GradeLetter(Enum):
    A = "A"
    B = "B"
    C = "C"


class GradeRank(IntEnum):
    A = 1
    B = 2
    C = 3


def main() -> None:
    lines = sys.stdin.read().splitlines()
    if not lines:
        return
    n = int(lines[0].strip())
    students: list[tuple[GradeRank, str]] = []
    for line in lines[1:1 + n]:
        name, grade, _age, _score = line.split()
        letter = GradeLetter(grade)
        rank = GradeRank[letter.name]
        students.append((rank, name))
    for rank, name in sorted(students, key=lambda item: item[0].value):
        print(f"{name} {rank.name} {rank.value}")


if __name__ == "__main__":
    main()
