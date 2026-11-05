"""Hybrid: the accelerated function takes and returns only ints, and CPython threads call it
with disjoint out[k] writes. This is the safe shape the hybrid is meant to accelerate."""
import threading


def combine(a: int, b: int) -> int:
    return a * 100 + b


def main():
    out = [0] * 8

    def worker(k):
        out[k] = combine(k, k + 1)

    ts = [threading.Thread(target=worker, args=(k,)) for k in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    total = 0
    for v in out:
        total += v
    print(len(out), total)


main()
