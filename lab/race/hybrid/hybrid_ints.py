"""Hybrid helper: an int-only typed function, built with `ail build --cpython`.

The threaded runner is `hybrid_ints_run.py`. The helper has no threading import so the hybrid
selector sees it as an ordinary module and accelerates `combine`; the runner then calls it from
CPython threads that write disjoint `out[k]` slots.
"""


def combine(a: int, b: int) -> int:
    return a * 100 + b
