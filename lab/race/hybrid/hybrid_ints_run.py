"""Hybrid: CPython threads call the accelerated int-only combine() with disjoint out[k] writes.

Run with `PYTHONPATH` pointing at the directory that holds hybrid_ints.py (plain CPython) or at
the output of `ail build --cpython hybrid_ints.py` (the extension).
"""
import threading

import hybrid_ints


def work(k: int, out: list[int]) -> None:
    out[k] = hybrid_ints.combine(k, k + 1)


def main():
    out = [0] * 8
    ts = [threading.Thread(target=work, args=(k, out)) for k in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    total = 0
    for v in out:
        total += v
    print(len(out), total)


main()
