"""Cases for par_sum (see spec.md). cases(rng) -> (public, hidden, perf).

Input: `N` on standard input. THREADS is the perf input's worker count; run_task.py reads it and
sets AIL_THREADS from it.

The exact sum over 1..N grows far slower than N (about 5e4 at N = 1e5 and -1.2e5 at N = 1e6), so no
runnable N makes it leave int64: the smallest N whose exact sum overflows is around 1e16, which the
task cannot iterate. `OVERFLOW_N` records that boundary for spec.md; it is not a runnable case.
"""
import importlib.util
from pathlib import Path

STDIN = True
THREADS = 4
PERF_N = 7000000
OVERFLOW_N = 10 ** 16
HERE = Path(__file__).resolve().parent


def ref():
    spec = importlib.util.spec_from_file_location('par_sum_ref', HERE / 'reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_checked = {}


def assert_int64(n):
    """The exact sum for n fits int64 (the int64 contract of every source), and steps() is exact."""
    if n in _checked:
        return _checked[n]
    if n <= 1_000_000:
        total = ref().solve(n)
        assert -(1 << 63) <= total < (1 << 63), 'the exact sum for n = %d is %d' % (n, total)
    _checked[n] = 1


def case(n):
    return b'%d\n' % n, []


def cases(rng):
    public = [
        ('small_parallel', *case(1000)),
        ('n0', *case(0)),
        ('n1', *case(1)),
        ('n7', *case(7)),
    ]
    hidden_n = [2, 3, 6, 8, 63, 64, 65, 1000, 4096, 99999, 100000, 200000, 1000000]
    hidden = [('n%d' % n, *case(n)) for n in hidden_n]
    hidden += [('n_odd', *case(123457)), ('threshold', *case(65536))]
    for _name, data, _args in hidden:
        assert_int64(int(data))
    perf = ('perf', *case(PERF_N))
    return public, hidden, perf
