import cmath
import math


def rotate(z: complex, degrees: float) -> complex:
    r, phi = cmath.polar(z)
    return cmath.rect(r, phi + math.radians(degrees))


def scale(z: complex, factor: float) -> complex:
    return cmath.rect(abs(z) * factor, cmath.phase(z))


def main() -> None:
    points: list[complex] = [complex(1.0, 0.0), complex(0.0, 1.0), complex(3.0, 4.0)]
    for z in points:
        print("start", repr(z), "x", z.real, "y", z.imag)
        for angle in [90.0, 180.0, -45.0]:
            moved = rotate(z, angle)
            print("  angle", angle, repr(moved), "r", abs(moved), "phi", cmath.phase(moved))
        print("  half", repr(scale(z, 0.5)))
    quarter = rotate(complex(2.0, 0.0), 90.0)
    print("quarter", repr(quarter), "close", cmath.isclose(quarter, complex(0.0, 2.0), abs_tol=1e-12))
    print("pythagoras", abs(complex(3.0, 4.0)), cmath.sqrt(abs(complex(3.0, 4.0))))


main()
