"""Hybrid helper: one bytearray function and one int function, built with `ail build --cpython`.

The threaded runner is `hybrid_bytearray_run.py`. The hybrid accepts int/float/bool/str/list[int]/
list[float] parameters; a `bytearray` parameter is not eligible, so `checksum` stays in CPython
while `tagged` is accelerated. The runner calls both from CPython threads.
"""


def checksum(buf: bytearray) -> int:
    s = 0
    for i in range(0, len(buf)):
        s = (s * 31 + buf[i]) % 1000003
    return s


def tagged(n: int) -> int:
    return n * 7 + 1
