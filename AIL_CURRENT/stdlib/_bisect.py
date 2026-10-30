"""The `_bisect` accelerator, written in the Python subset: what CPython's C module does, error texts included.

bisect.py runs `from _bisect import *`, so CPython's bisect_left/... are the C ones. They differ from bisect.py's
pure-Python ones in how `lo` and `hi` are read: an int is required (`TypeError: 'str' object cannot be
interpreted as an integer`, `argument should be integer or None, not 'str'`), `hi=-1` means len(a), and
`lo < 0` is `ValueError: lo must be non-negative`. Not matched: an index given as an object with `__index__`, the
text of a call with the wrong number of arguments (the compiler refuses such a call).
"""
__all__ = ['bisect_left', 'bisect_right', 'insort_left', 'insort_right']


def _tn(x):
    name = type(x).__name__
    if name == '_ail_object':
        return 'object'          # the compiler's object() sentinel
    return name


def _lo(lo):
    if not isinstance(lo, int):
        raise TypeError("'" + _tn(lo) + "' object cannot be interpreted as an integer")
    return lo + 0


def _hi(hi):
    if hi is None:
        return -1
    if not isinstance(hi, int):
        raise TypeError("argument should be integer or None, not '" + _tn(hi) + "'")
    return hi


def _bounds(a, lo, hi):
    lo = _lo(lo)
    hi = _hi(hi)
    if lo < 0:
        raise ValueError('lo must be non-negative')
    if hi == -1:
        hi = len(a)
    return lo, hi


def bisect_right(a, x, lo=0, hi=None, *, key=None):
    lo, hi = _bounds(a, lo, hi)
    if key is None:
        while lo < hi:
            mid = (lo + hi) // 2
            if x < a[mid]:
                hi = mid
            else:
                lo = mid + 1
    else:
        while lo < hi:
            mid = (lo + hi) // 2
            if x < key(a[mid]):
                hi = mid
            else:
                lo = mid + 1
    return lo


def bisect_left(a, x, lo=0, hi=None, *, key=None):
    lo, hi = _bounds(a, lo, hi)
    if key is None:
        while lo < hi:
            mid = (lo + hi) // 2
            if a[mid] < x:
                lo = mid + 1
            else:
                hi = mid
    else:
        while lo < hi:
            mid = (lo + hi) // 2
            if key(a[mid]) < x:
                lo = mid + 1
            else:
                hi = mid
    return lo


def insort_right(a, x, lo=0, hi=None, *, key=None):
    if key is None:
        index = bisect_right(a, x, lo, hi)
    else:
        index = bisect_right(a, key(x), lo, hi, key=key)
    a.insert(index, x)


def insort_left(a, x, lo=0, hi=None, *, key=None):
    if key is None:
        index = bisect_left(a, x, lo, hi)
    else:
        index = bisect_left(a, key(x), lo, hi, key=key)
    a.insert(index, x)
