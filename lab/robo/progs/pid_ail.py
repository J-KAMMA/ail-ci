"""AIL version of the 1 kHz jitter loop (mirrors progs/pid.c).

AIL has no clock_nanosleep, so the loop keeps an absolute deadline in
perf_counter() seconds and sleeps the remaining time with time.sleep(). The
PID update is inlined and the misses go into a 1-microsecond histogram, so the
program stays on the typed path.

Run: ./pid_ail [iters] [noalloc|alloc]
"""

import sys
import time

N = 8
PERIOD = 0.001
BUCKETS = 20001


def percentile(hist: list[int], iters: int, num: int, den: int) -> int:
    want = iters * num // den
    cum = 0
    b = 0
    while b < BUCKETS:
        cum += hist[b]
        if cum > want:
            return b
        b += 1
    return BUCKETS - 1


def main() -> None:
    iters = 20000
    allocating = False
    if len(sys.argv) > 1:
        iters = int(sys.argv[1])
    if len(sys.argv) > 2 and sys.argv[2] == "alloc":
        allocating = True

    state: list[float] = [0.0] * N
    integral: list[float] = [0.0] * N
    prev: list[float] = [0.0] * N
    hist: list[int] = [0] * BUCKETS
    setpoint: list[float] = [1.0, 0.5, 0.0, -0.5, -1.0, 0.25, 0.75, -0.25]

    deadline = time.perf_counter()
    max_miss = 0.0
    overruns = 0
    for i in range(iters):
        deadline = deadline + PERIOD
        k = 0
        while k < N:
            err = setpoint[k] - state[k]
            integral[k] = integral[k] + err * 0.005
            deriv = (err - prev[k]) / 0.005
            prev[k] = err
            u = 0.85 * err + 0.12 * integral[k] + 0.04 * deriv
            if u > 2.0:
                u = 2.0
            if u < -2.0:
                u = -2.0
            state[k] = state[k] + (u - 0.3 * state[k]) * 0.005
            k += 1
        if allocating:
            tmp = list(state)
            total = 0.0
            for j in range(N):
                total = total + tmp[j]
            state[0] = state[0] + total * 0.0

        remaining = deadline - time.perf_counter()
        if remaining > 0.0:
            time.sleep(remaining)
        miss = (time.perf_counter() - deadline) * 1000000.0
        if miss > max_miss:
            max_miss = miss
        b = int(miss)
        if b < 0:
            b = 0
        if b >= BUCKETS:
            b = BUCKETS - 1
        hist[b] = hist[b] + 1
        if miss >= 1000.0:
            overruns += 1

    print("iters", iters)
    print("p50", percentile(hist, iters, 50, 100))
    print("p99", percentile(hist, iters, 99, 100))
    print("p999", percentile(hist, iters, 999, 1000))
    print("max", round(max_miss, 3))
    print("overruns", overruns)


main()
