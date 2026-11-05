"""Hybrid helper: a typed list[int] reader, built with `ail build --cpython`.

The threaded runner is `hybrid_list_append_run.py`. Reading a list parameter is eligible for the
hybrid, whose native call releases the GIL; another CPython thread appends to that same list while
the accelerated `total` walks it. The probe prints only facts that do not depend on the interleaving.
"""


def total(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s += x
    return s
