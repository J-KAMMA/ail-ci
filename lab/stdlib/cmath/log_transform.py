import cmath


def transform(values: list[complex], base: float) -> list[complex]:
    out: list[complex] = []
    for value in values:
        if base == 10.0:
            out.append(cmath.log10(value))
        else:
            out.append(cmath.log(value, base))
    return out


def main() -> None:
    samples: list[complex] = [complex(1.0, 0.0), complex(2.0, 0.0), complex(1.0, 1.0),
                              complex(-1.0, 0.0), complex(0.0, 0.0)]
    base = 10.0
    for z in samples:
        try:
            natural = cmath.log(z)
            common = cmath.log10(z)
            custom = cmath.log(z, base)
            print(repr(z), repr(natural), repr(common), repr(custom))
        except ValueError as exc:
            print(repr(z), "domain error:", exc)
    ok = [complex(10.0, 0.0), complex(100.0, 0.0)]
    print("base 10", [repr(x) for x in transform(ok, 10.0)])
    print("base 2", [repr(x) for x in transform([complex(8.0, 0.0)], 2.0)])
    print("empty", transform([], 10.0))
    try:
        print(cmath.log(complex(0.0, 0.0)))
    except ValueError as exc:
        print("zero log:", exc)
    print("identity", cmath.isclose(cmath.exp(cmath.log(complex(3.0, 4.0))), complex(3.0, 4.0), rel_tol=1e-12))


main()
