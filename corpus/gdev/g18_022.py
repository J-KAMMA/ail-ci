# task: Use namedtuple._replace and _asdict to update fields of hardcoded records and print the updated records as dictionaries.
from collections import namedtuple
from typing import NamedTuple


class Employee(NamedTuple):
    name: str
    department: str
    salary: int
    active: bool


Point = namedtuple("Point", ["x", "y", "label"])


def describe(record: tuple) -> dict:
    return record._asdict()


def main() -> None:
    # Hardcoded original records
    alice = Employee(name="Alice", department="Engineering", salary=95000, active=True)
    bob = Employee(name="Bob", department="Marketing", salary=70000, active=False)
    carol = Employee(name="Carol", department="Sales", salary=82000, active=True)

    print("Original records:")
    for emp in (alice, bob, carol):
        print(describe(emp))

    # Update fields using _replace (returns new immutable records)
    alice_promoted = alice._replace(department="Management", salary=110000)
    bob_reactivated = bob._replace(active=True)
    carol_raised = carol._replace(salary=carol.salary + 5000)

    print()
    print("Updated records:")
    for emp in (alice_promoted, bob_reactivated, carol_raised):
        print(describe(emp))

    # The originals remain unchanged
    print()
    print("Originals still intact:")
    print(alice._asdict())
    print(bob._asdict())

    # Same idea with a namedtuple created via the functional form
    p1 = Point(x=1, y=2, label="origin-ish")
    p2 = p1._replace(x=10, label="moved")

    print()
    print("Point before:", describe(p1))
    print("Point after: ", describe(p2))

    # Build a dictionary of updated values from a record
    fields_changed = {
        key: value
        for key, value in alice_promoted._asdict().items()
        if getattr(alice, key) != value
    }
    print()
    print("Fields changed for Alice:", fields_changed)


if __name__ == "__main__":
    main()
