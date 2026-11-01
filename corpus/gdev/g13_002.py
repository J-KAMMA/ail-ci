# task: Implement a Vehicle base class with wheels and speed attributes, derive Car and Bicycle subclasses with different defaults, and print their descriptions.
from __future__ import annotations


class Vehicle:
    """A generic vehicle with a number of wheels and a speed."""

    default_wheels: int = 0
    default_speed: float = 0.0
    kind: str = "vehicle"

    def __init__(self, wheels: int | None = None, speed: float | None = None) -> None:
        self.wheels: int = self.default_wheels if wheels is None else wheels
        self.speed: float = self.default_speed if speed is None else speed

    def describe(self) -> str:
        return f"{self.kind.capitalize()} with {self.wheels} wheels, speed {self.speed:.1f} km/h"


class Car(Vehicle):
    """A car: four wheels and a higher default speed."""

    default_wheels: int = 4
    default_speed: float = 120.0
    kind: str = "car"


class Bicycle(Vehicle):
    """A bicycle: two wheels and a lower default speed."""

    default_wheels: int = 2
    default_speed: float = 25.0
    kind: str = "bicycle"


def main() -> None:
    vehicles: list[Vehicle] = [
        Vehicle(),
        Car(),
        Bicycle(),
        Car(speed=95.5),
        Bicycle(wheels=3, speed=10.0),
    ]
    for vehicle in vehicles:
        print(vehicle.describe())


if __name__ == "__main__":
    main()
