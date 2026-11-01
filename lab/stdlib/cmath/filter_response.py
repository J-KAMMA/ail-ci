import cmath
import math


def response(frequency: float, cutoff: float, damping: float) -> complex:
    w = frequency / cutoff
    return 1.0 / (1.0 + complex(0.0, 1.0) * (w / damping))


def decibels(value: float) -> float:
    if value == 0.0:
        return cmath.log10(complex(0.0, 0.0)).real
    return 20.0 * math.log10(value)


def main() -> None:
    cutoff = 1000.0
    damping = 0.707
    frequencies = [10.0, 100.0, 500.0, 1000.0, 2000.0, 10000.0]
    for f in frequencies:
        h = response(f, cutoff, damping)
        magnitude = abs(h)
        db = decibels(magnitude)
        phase = cmath.phase(h)
        print(f, repr(h), "gain", db, "phase", phase)
    h = response(1000.0, cutoff, damping)
    print("cutoff gain", abs(h), "expected", 1.0 / math.sqrt(2.0))
    print("close", cmath.isclose(abs(h), 1.0 / math.sqrt(2.0), rel_tol=1e-3, abs_tol=0.0))
    print("log", repr(cmath.log(complex(1000.0, 1000.0))))
    print("log10", repr(cmath.log(complex(1000.0, 1000.0), 10.0)))


main()
