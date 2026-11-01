import cmath
import math


def oscillator(amplitude: float, decay: float, omega: float, t: float) -> complex:
    return amplitude * cmath.exp(complex(-decay * t, omega * t))


def main() -> None:
    times = [0.0, 0.25, 0.5, 1.0, 2.0]
    total = complex(0.0, 0.0)
    for t in times:
        wave = oscillator(2.0, 0.3, 2.0 * math.pi, t)
        total = total + wave
        print(t, repr(wave), "abs", abs(wave), "phase", cmath.phase(wave))
    print("sum", repr(total), "abs", abs(total), "phase", cmath.phase(total))
    print("polar", repr(cmath.polar(total)))
    print("rect back", repr(cmath.rect(abs(total), cmath.phase(total))))
    print("rotating", repr(oscillator(1.0, 0.0, math.pi / 2.0, 1.0)))
    print("close", cmath.isclose(cmath.rect(abs(total), cmath.phase(total)), total, rel_tol=1e-12))
    print("log magnitude", repr(cmath.log(abs(total))))
    print("exp of log", repr(cmath.exp(cmath.log(total))))


main()
