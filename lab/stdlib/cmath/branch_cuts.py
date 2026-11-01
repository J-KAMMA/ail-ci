import cmath


def report(label: str, z: complex) -> None:
    root = cmath.sqrt(z)
    print(label, repr(z), "sqrt", repr(root), "square", repr(root * root))
    print("  finite", cmath.isfinite(z), "nan", cmath.isnan(z), "inf", cmath.isinf(z))


def main() -> None:
    report("positive", complex(4.0, 0.0))
    report("negative", complex(-4.0, 0.0))
    report("below cut", complex(-4.0, -0.0))
    report("negative zero", complex(0.0, -0.0))
    report("pure imaginary", complex(0.0, 4.0))
    report("infinity", complex(float('inf'), 0.0))
    report("nan", complex(float('nan'), 0.0))
    for z in [complex(-1.0, 0.0), complex(-1.0, -0.0), complex(3.0, 4.0)]:
        root = cmath.sqrt(z)
        print("branch", repr(z), repr(root), "phase", cmath.phase(root))
    print("polar cut", repr(cmath.polar(complex(-1.0, -0.0))))
    print("isfinite inf", cmath.isfinite(cmath.inf), cmath.isfinite(cmath.infj))
    print("isnan nanj", cmath.isnan(cmath.nanj), cmath.isinf(cmath.infj))
    print("sqrt infj", repr(cmath.sqrt(cmath.infj)), repr(cmath.sqrt(cmath.nanj)))


main()
