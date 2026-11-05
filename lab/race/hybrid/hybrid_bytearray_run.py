"""Hybrid: CPython threads call a bytearray checksum (kept in CPython) and an accelerated int
function. Sorting before printing keeps the output deterministic."""
import threading

import hybrid_bytearray


def scan(buf: bytearray, got: list[int]) -> None:
    got.append(hybrid_bytearray.checksum(buf))


def tag(n: int, got: list[int]) -> None:
    got.append(hybrid_bytearray.tagged(n))


def main():
    buf = bytearray(range(256))
    got = []
    ts = [threading.Thread(target=scan, args=(buf, got)) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    for k in range(4):
        t = threading.Thread(target=tag, args=(k, got))
        t.start()
        t.join()
    print(len(got), sorted(got)[0], sorted(got)[-1], len(set(got)))


main()
