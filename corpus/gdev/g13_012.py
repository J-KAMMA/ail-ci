# task: Define a Person class with a __str__ method and a Student subclass that extends the string representation, printing both for fixed instances.
from __future__ import annotations


class Person:
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

    def __str__(self) -> str:
        return f"Person(name={self.name!r}, age={self.age})"


class Student(Person):
    def __init__(self, name: str, age: int, school: str, grade: int) -> None:
        super().__init__(name, age)
        self.school = school
        self.grade = grade

    def __str__(self) -> str:
        base = super().__str__()
        return f"{base} -> Student(school={self.school!r}, grade={self.grade})"


def main() -> None:
    person = Person("Alice", 34)
    student = Student("Bob", 19, "Riverside High", 11)

    print(person)
    print(student)


if __name__ == "__main__":
    main()
