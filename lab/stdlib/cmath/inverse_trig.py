import cmath


def round_trip(z: complex) -> None:
    try:
        s = cmath.asin(z)
        c = cmath.acos(z)
        t = cmath.atan(z)
        print(repr(z), "asin", repr(s), "acos", repr(c), "atan", repr(t))
        print("  back", repr(cmath.sin(s)), repr(cmath.cos(c)), repr(cmath.tan(t)))
        print("  close", cmath.isclose(cmath.sin(s), z, rel_tol=1e-12, abs_tol=1e-15))
    except ValueError as exc:
        print(repr(z), "domain error:", exc)


def hyperbolic(z: complex) -> None:
    try:
        print(repr(z), "asinh", repr(cmath.asinh(z)), "acosh", repr(cmath.acosh(z)),
              "atanh", repr(cmath.atanh(z)))
    except ValueError as exc:
        print(repr(z), "hyperbolic domain error:", exc)


def main() -> None:
    values: list[complex] = [complex(0.0, 0.0), complex(0.5, 0.0), complex(2.0, 0.0),
                             complex(1.0, 1.0), complex(3.0, -1.0)]
    for z in values:
        round_trip(z)
    for z in [complex(0.5, 0.0), complex(0.0, 1.0), complex(-2.0, 0.0)]:
        hyperbolic(z)
    try:
        print(cmath.atanh(complex(1.0, 0.0)))
    except ValueError as exc:
        print("atanh one:", exc)
    try:
        print(cmath.acosh(complex(-1.0, 0.0)))
    except ValueError as exc:
        print("acosh minus one:", exc)
    print("asin i", repr(cmath.asin(complex(0.0, 1.0))))
    print("acos i", repr(cmath.acos(complex(0.0, 1.0))))


main()
