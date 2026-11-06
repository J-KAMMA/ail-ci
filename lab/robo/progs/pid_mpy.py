"""MicroPython unix-port version of the 1 kHz jitter loop (mirrors progs/pid.c).

Absolute deadlines are kept in a nanosecond integer; MicroPython's sleep is
relative, so the loop sleeps the remaining time to the absolute deadline.

Run: micropython pid_mpy.py [iters] [noalloc|alloc]
"""

import sys
import time

N = 8
PERIOD_NS = 1000000
BUCKETS = 20001
SETPOINT = [1.0, 0.5, 0.0, -0.5, -1.0, 0.25, 0.75, -0.25]


def percentile(hist, iters, num, den):
    want = iters * num // den
    cum = 0
    b = 0
    while b < BUCKETS:
        cum += hist[b]
        if cum > want:
            return b
        b += 1
    return BUCKETS - 1


def main():
    iters = 20000
    allocating = False
    if len(sys.argv) > 1:
        iters = int(sys.argv[1])
    if len(sys.argv) > 2 and sys.argv[2] == "alloc":
        allocating = True

    state = [0.0] * N
    integral = [0.0] * N
    prev = [0.0] * N
    hist = [0] * BUCKETS

    deadline = time.time_ns()
    max_miss = 0.0
    overruns = 0
    for i in range(iters):
        deadline += PERIOD_NS
        k = 0
        while k < N:
            err = SETPOINT[k] - state[k]
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
                total += tmp[j]
            state[0] += total * 0.0

        now = time.time_ns()
        remaining = deadline - now
        if remaining > 0:
            time.sleep_us(remaining // 1000)
        miss = (time.time_ns() - deadline) / 1000.0
        if miss > max_miss:
            max_miss = miss
        b = int(miss)
        if b < 0:
            b = 0
        if b >= BUCKETS:
            b = BUCKETS - 1
        hist[b] += 1
        if miss >= 1000.0:
            overruns += 1

    print("iters", iters)
    print("p50", percentile(hist, iters, 50, 100))
    print("p99", percentile(hist, iters, 99, 100))
    print("p999", percentile(hist, iters, 999, 1000))
    print("max", round(max_miss, 3))
    print("overruns", overruns)


main()
