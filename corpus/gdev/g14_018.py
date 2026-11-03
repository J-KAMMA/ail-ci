# task: Build a dataclass hierarchy where a base Animal class has a subclass Dog adding a field, and print the combined field order.
from dataclasses import dataclass, fields


@dataclass
class Animal:
    name: str
    age: int = 0


@dataclass
class Dog(Animal):
    breed: str = "unknown"


def main() -> None:
    dog = Dog(name="Rex", age=3, breed="Labrador")
    field_names = [f.name for f in fields(Dog)]
    print("Combined field order:", ", ".join(field_names))
    print("Instance:", dog)


if __name__ == "__main__":
    main()
