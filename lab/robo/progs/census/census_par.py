"""Census probe: par_range (parallel loop). This stays on the typed path; bare
metal stops at the pool's clock (CLOCK_MONOTONIC/clock_gettime), then at the
PTHREAD_*_INITIALIZER macros newlib omits when _POSIX_THREADS is off."""

from ail import par_range


def main() -> None:
    out: list[int] = [0] * 100
    for i in par_range(0, 100):
        out[i] = i * 2
    total = 0
    for i in range(100):
        total += out[i]
    print(total)


main()
