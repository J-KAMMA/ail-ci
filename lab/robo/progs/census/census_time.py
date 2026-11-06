"""Census probe: clock and sleeping (clock_gettime, nanosleep)."""

import time


def main() -> None:
    t0 = time.perf_counter()
    time.sleep(0.001)
    t1 = time.perf_counter()
    print("slept", t1 > t0)
    print("wall", time.time_ns() > 0)


main()
