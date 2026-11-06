"""Census probe: par_range (parallel loop). This stays on the typed path and is
the cleanest pthread blocker: newlib-nano's pthread.h has no pthread_mutex_t."""

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
