"""Cases for par_collatz (see spec.md). cases(rng) -> (public, hidden, perf).

Input: `N W` on standard input. THREADS is the perf input's worker count; run_task.py reads it and
sets AIL_THREADS from it.
"""
import importlib.util
from pathlib import Path

STDIN = True
THREADS = 4
PERF_N = 7000000
HERE = Path(__file__).resolve().parent


def ref():
    spec = importlib.util.spec_from_file_location('par_collatz_ref', HERE / 'reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_peaks = {}


def assert_int64(n):
    """The largest value the Collatz map reaches for m <= n, and the int64 assertion of the spec.

    Trajectories are shared, so a value already on a walked trajectory is marked: the sweep over 1..n costs
    a few seconds at the perf size instead of a full recomputation per n.
    """
    if n in _peaks:
        return _peaks[n]
    seen = bytearray(n + 1)
    seen[0] = seen[1] = 1
    peak = 0
    for k in range(2, n + 1):
        if seen[k]:
            continue
        m = k
        path = []
        while not (m <= n and seen[m]):
            if m > peak:
                peak = m
            path.append(m)
            m = 3 * m + 1 if m & 1 else m >> 1
        for v in path:
            if v <= n:
                seen[v] = 1
    assert peak < 1 << 63, 'the Collatz map reaches %d > 2^63 for n <= %d' % (peak, n)
    _peaks[n] = peak
    return peak


def case(n, w):
    return b'%d %d\n' % (n, w), []


def cases(rng):
    public = [
        ('small_parallel', *case(1000, THREADS)),
        ('n1_w1', *case(1, 1)),
        ('w_gt_n', *case(3, 8)),
        ('w1_1000', *case(1000, 1)),
    ]
    hidden_n = [2, 5, 64, 65, 1000, 4096, 100000, 200000]
    hidden = [('n%d_w1' % n, *case(n, 1)) for n in hidden_n]
    hidden += [
        ('w2', *case(50000, 2)),
        ('w3_odd', *case(99999, 3)),
        ('w7', *case(200000, 7)),
        ('w_eq_n', *case(8, 8)),
        ('w_gt_n_big', *case(10, 9)),
        ('w8', *case(131072, 8)),
        ('powers_of_two', *case(1 << 17, 6)),
        ('n_odd', *case(123457, 4)),
        ('n_three', *case(3, 4)),
    ]
    for name, data, args in hidden:
        n, _w = (int(x) for x in data.split())
        assert_int64(n)
    assert_int64(PERF_N)
    perf = ('perf', *case(PERF_N, THREADS))
    return public, hidden, perf
