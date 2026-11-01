from enum import Enum


class Planet(Enum):
    MERCURY = (3.301e23, 2.4397e6)
    EARTH = (5.972e24, 6.371e6)

    def __init__(self, mass, radius):
        self.mass = mass
        self.radius = radius

    def gravity(self):
        return self.mass / (self.radius * self.radius)


def main():
    print(Planet.EARTH.value)
    print(Planet.MERCURY.mass, Planet.MERCURY.radius)
    print(round(Planet.EARTH.gravity(), 3))


main()
