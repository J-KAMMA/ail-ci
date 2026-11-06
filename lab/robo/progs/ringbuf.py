"""Fixed-size sensor ring buffer with a moving average.

2000 deterministic samples; no imports, no allocation in steady state.
"""

SIZE = 8


def sample(i: int) -> float:
    # A deterministic sensor-like signal: a slow ramp plus a small zig-zag.
    base = i % 37
    ripple = i % 5
    return base * 0.25 - ripple * 0.5


def main() -> None:
    buf: list[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    head = 0
    count = 0
    total = 0.0
    checksum = 0.0
    peak = 0.0
    for i in range(2000):
        value = sample(i)
        if count == SIZE:
            total = total - buf[head]
        else:
            count += 1
        buf[head] = value
        total = total + value
        head = (head + 1) % SIZE
        avg = total / count
        if avg > peak:
            peak = avg
        if i % 97 == 0:
            checksum = checksum + avg
    print("count", count)
    print("head", head)
    print("average", round(total / count, 6))
    print("peak", round(peak, 6))
    print("checksum", round(checksum, 6))
    for k in range(SIZE):
        print("slot", k, round(buf[k], 6))


main()
