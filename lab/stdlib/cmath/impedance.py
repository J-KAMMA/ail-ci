import cmath
import math


def series(first: complex, second: complex) -> complex:
    return first + second


def parallel(first: complex, second: complex) -> complex:
    return 1.0 / (1.0 / first + 1.0 / second)


def describe(name: str, z: complex) -> None:
    magnitude = abs(z)
    angle = cmath.phase(z)
    r, phi = cmath.polar(z)
    print(name, repr(z), "|Z|", magnitude, "phase", angle)
    print(name, "polar", (r, phi), "degrees", math.degrees(phi))


def main() -> None:
    names: list[str] = ["coil", "capacitor", "combination"]
    coil = complex(3.0, 4.0)
    capacitor = complex(3.0, -4.0)
    zs: list[complex] = [coil, capacitor, parallel(coil, capacitor)]
    for index in range(len(names)):
        describe(names[index], zs[index])
    print("series", repr(series(coil, capacitor)))
    total = complex(0.0, 0.0)
    for z in zs:
        total = total + z
    print("sum", repr(total), "average", repr(total / len(zs)))
    print("matches coil", cmath.isclose(zs[2], coil, rel_tol=1e-12))
    print("angle difference", cmath.phase(coil) - cmath.phase(capacitor))


main()
