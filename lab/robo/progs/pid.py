"""PID controller over a fixed list of setpoints; prints the final state.

Runs unchanged under CPython 3.12 and AIL (--syntax python). Every arithmetic
step is a plain IEEE double operation so the output is comparable across
x86-64, aarch64 and armhf.
"""

KP = 0.85
KI = 0.12
KD = 0.04
DT = 0.005

SETPOINTS = [1.0, 0.5, 0.0, -0.5, -1.0, 0.25, 0.75, -0.25]


def clamp(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def main() -> None:
    state: list[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    integral: list[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    prev: list[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    steps = 0
    for target in SETPOINTS:
        for _ in range(500):
            k = 0
            while k < 8:
                err = target - state[k]
                integral[k] = integral[k] + err * DT
                deriv = (err - prev[k]) / DT
                prev[k] = err
                u = clamp(KP * err + KI * integral[k] + KD * deriv, -2.0, 2.0)
                state[k] = state[k] + (u - 0.3 * state[k]) * DT
                k += 1
            steps += 1
    total = 0.0
    for k in range(8):
        total = total + state[k]
    print("steps", steps)
    print("state", round(total, 6))
    for k in range(8):
        print("x", k, round(state[k], 6))
    print("integral", round(integral[0], 6), round(integral[7], 6))
    print("prev", round(prev[0], 6), round(prev[7], 6))


main()
