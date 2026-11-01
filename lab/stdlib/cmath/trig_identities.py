import cmath


def check_sin_cos(z: complex) -> bool:
    left = cmath.sin(z) ** 2 + cmath.cos(z) ** 2
    return cmath.isclose(left, complex(1.0, 0.0), rel_tol=1e-12, abs_tol=1e-15)


def check_cosh_sinh(z: complex) -> bool:
    left = cmath.cosh(z) ** 2 - cmath.sinh(z) ** 2
    return cmath.isclose(left, complex(1.0, 0.0), rel_tol=1e-12, abs_tol=1e-15)


def main() -> None:
    values: list[complex] = [complex(0.0, 0.0), complex(1.0, 0.0), complex(0.0, 1.0),
                             complex(1.0, 2.0), complex(-2.0, 0.5)]
    for z in values:
        print(repr(z), "sin", repr(cmath.sin(z)), "cos", repr(cmath.cos(z)), "tan", repr(cmath.tan(z)))
        print("  sinh", repr(cmath.sinh(z)), "cosh", repr(cmath.cosh(z)), "tanh", repr(cmath.tanh(z)))
        print("  sin^2+cos^2", check_sin_cos(z), "cosh^2-sinh^2", check_cosh_sinh(z))
    z = complex(0.5, -0.25)
    print("tan ratio", cmath.isclose(cmath.tan(z), cmath.sin(z) / cmath.cos(z), rel_tol=1e-12))
    print("tanh ratio", cmath.isclose(cmath.tanh(z), cmath.sinh(z) / cmath.cosh(z), rel_tol=1e-12))
    print("sin odd", cmath.isclose(cmath.sin(-z), -cmath.sin(z), rel_tol=1e-12))
    print("cos even", cmath.isclose(cmath.cos(-z), cmath.cos(z), rel_tol=1e-12))


main()
