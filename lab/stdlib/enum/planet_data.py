from enum import Enum


class Planet(Enum):
    MERCURY = (3.301e23, 2.4397e6)
    VENUS = (4.867e24, 6.0518e6)
    EARTH = (5.972e24, 6.371e6)

    def mass(self):
        return self.value[0]

    def radius(self):
        return self.value[1]

    def gravity(self):
        return self.mass() / (self.radius() * self.radius())


def main():
    for planet in Planet:
        print(planet.name, planet.mass(), planet.radius(), round(planet.gravity(), 3))
    print(Planet.EARTH.value, Planet((5.972e24, 6.371e6)))
    print(Planet.MERCURY.value[0], Planet.EARTH.value[1])
    lookup = {(5.972e24, 6.371e6): "home"}
    print(lookup[Planet.EARTH.value])
    print(sorted(Planet, key=lambda body: body.mass())[0].name)
    try:
        Planet((1.0, 2.0))
    except ValueError as error:
        print("ValueError", error)


main()
