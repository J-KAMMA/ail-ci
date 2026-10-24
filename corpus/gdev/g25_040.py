# task: Define an Enum for planets with mass attributes and print the planet names sorted by mass for a fixed set of members.
from enum import Enum


class Planet(Enum):
    """Planets of the solar system with their masses in kilograms."""

    MERCURY = 3.3011e23
    VENUS = 4.8675e24
    EARTH = 5.9720e24
    MARS = 6.4171e23
    JUPITER = 1.8982e27
    SATURN = 5.6834e26
    URANUS = 8.6810e25
    NEPTUNE = 1.02413e26

    @property
    def mass(self) -> float:
        """Mass of the planet in kilograms."""
        return self.value


def main() -> None:
    planets_by_mass = sorted(Planet, key=lambda planet: planet.mass)
    print("Planets sorted by mass (lightest first):")
    for rank, planet in enumerate(planets_by_mass, start=1):
        print(f"{rank}. {planet.name.title():<8} {planet.mass:.4e} kg")


if __name__ == "__main__":
    main()
