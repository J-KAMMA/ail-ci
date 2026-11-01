import math

def classify(value):
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf"
    if math.isfinite(value):
        return "finite"
    return "other"

def main():
    inf = math.inf
    nan = math.nan
    print(classify(inf), classify(-inf), classify(nan), classify(1.0))
    print("copysign", math.copysign(3.0, -0.0), math.copysign(-3.0, 0.0))
    print("fmod", math.fmod(7.5, 2.0), math.fmod(-7.5, 2.0))
    print("remainder", math.remainder(7.0, 3.0), math.remainder(8.0, 3.0))
    print("next", math.nextafter(1.0, 2.0), math.nextafter(1.0, 0.0))
    print("close", math.isclose(0.1 + 0.2, 0.3), math.isclose(1.0, 1.001, rel_tol=1e-2))
    print("nan compare", nan == nan, math.isnan(nan))
    try:
        print(math.fmod(1.0, 0.0))
    except ValueError as exc:
        print("fmod failed:", exc)
    try:
        print(math.remainder(1.0, 0.0))
    except ValueError as exc:
        print("remainder failed:", exc)

main()
