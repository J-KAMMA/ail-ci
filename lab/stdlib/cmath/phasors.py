import cmath
import math


def phasor(rms: float, degrees: float) -> complex:
    return cmath.rect(rms, math.radians(degrees))


def combine(values: list[complex]) -> complex:
    total = complex(0.0, 0.0)
    for value in values:
        total = total + value
    return total


def main() -> None:
    angles = [0.0, 120.0, 240.0]
    amplitudes = [120.0, 120.0, 120.0]
    values: list[complex] = []
    for i in range(len(angles)):
        values.append(phasor(amplitudes[i], angles[i]))
    for i in range(len(values)):
        print(angles[i], repr(values[i]), "rms", abs(values[i]), "phase", cmath.phase(values[i]))
    total = combine(values)
    print("balanced sum", repr(total), "rms", abs(total))
    rotated = cmath.rect(abs(values[0]), cmath.phase(values[0]) + math.pi / 2.0)
    print("rotated", repr(rotated))
    print("difference", repr(values[0] - values[1]), "abs", abs(values[0] - values[1]))
    print("expected line voltage", repr(cmath.sqrt(3.0) * 120.0))
    print("close", cmath.isclose(abs(values[0] - values[1]), cmath.sqrt(3.0) * 120.0, rel_tol=1e-12))
    print("empty", repr(combine([])))


main()
