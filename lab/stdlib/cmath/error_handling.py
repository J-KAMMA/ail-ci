import cmath


def mean(values: list[complex]) -> complex:
    if len(values) == 0:
        return complex(0.0, 0.0)
    total = complex(0.0, 0.0)
    for value in values:
        total = total + value
    return total / len(values)


def show(label: str, value: complex) -> None:
    print(label, repr(value), "abs", abs(value), "phase", cmath.phase(value))


def main() -> None:
    empty: list[complex] = []
    show("empty mean", mean(empty))
    print("empty polar", repr(cmath.polar(complex(0.0, 0.0))))
    for z in [complex(0.0, 0.0), complex(0.0, -0.0)]:
        try:
            print("log", repr(cmath.log(z)))
        except ValueError as exc:
            print("log domain:", exc)
        try:
            print("log10", repr(cmath.log10(z)))
        except ValueError as exc:
            print("log10 domain:", exc)
    try:
        print(cmath.exp(complex(1000.0, 0.0)))
    except OverflowError as exc:
        print("exp overflow:", exc)
    try:
        print(cmath.cosh(complex(1000.0, 0.0)))
    except OverflowError as exc:
        print("cosh overflow:", exc)
    try:
        print(cmath.rect(1.0, float('inf')))
    except ValueError as exc:
        print("rect domain:", exc)
    try:
        print(cmath.polar(complex(1e308, 1e308)))
    except OverflowError as exc:
        print("polar overflow:", exc)
    try:
        print(cmath.isclose(complex(1.0, 1.0), complex(2.0, 2.0), abs_tol=-1.0))
    except ValueError as exc:
        print("isclose tolerance:", exc)
    print("finite", cmath.isfinite(complex(1.0, 2.0)), cmath.isnan(cmath.nanj))


main()
