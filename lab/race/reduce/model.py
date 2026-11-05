#!/usr/bin/env python3
"""Reference model of the exact shared-int reduction (docs/design/PAR_REDUCE.md, D1 option c).

    python3 lab/race/reduce/model.py [cases]

A sequential simulation is the oracle.  The model under test is the chunked combine: per chunk the
partial sum S_c, the largest prefix M_c and the smallest prefix m_c in unbounded ints (the C code
uses __int128), the chunk's first exception; then a combine on the calling thread in chunk order.

Two shapes are modelled:

* `acc += e` in a parallel body.  Items are ("v", int) or ("x", kind).  The calling thread runs a
  probe prefix sequentially with the checked int64 add; the wide phase starts from the value the
  prefix left.  A chunk whose B + M_c or B + m_c leaves int64 is re-run alone, sequentially, from B;
  otherwise its first exception is raised; otherwise B += S_c.
* `acc = sum(ex.map(f, xs))` / `sum(pool.map(f, xs))`.  The map runs first: the first exception of f
  in iteration order wins over any overflow, and only then does the sequential sum stop at its first
  overflowing prefix.

The comparison key is (exception kind or None, the iteration where the run stops, acc after the
run).  The two must agree on every case; 200,000 random cases with a fixed seed print 0 differences.
"""
import random
import sys

INT64_MAX = (1 << 63) - 1
INT64_MIN = -(1 << 63)


# -- the sequential oracle ----------------------------------------------------------------------
def seq_from(items, lo, hi, acc):
    """The plain checked int64 loop over items[lo:hi], starting from acc."""
    for k in range(lo, hi):
        kind, value = items[k]
        if kind == 'x':
            return (value, k, acc)
        grown = acc + value
        if grown > INT64_MAX or grown < INT64_MIN:
            return ('OverflowError', k, acc)
        acc = grown
    return (None, hi, acc)


def sequential(items, start):
    return seq_from(items, 0, len(items), start)


def sequential_map_sum(items, start=0):
    """`acc = sum(map(f, xs))`: the map runs to completion first, then a left-to-right sum."""
    for k in range(len(items)):
        if items[k][0] == 'x':
            return (items[k][1], k, start)
    return seq_from(items, 0, len(items), start)


# -- the chunked combine ------------------------------------------------------------------------
def chunk_stats(items, lo, hi):
    """(S, M, m, first exception, completed prefixes) for one chunk, in unbounded ints."""
    total = 0
    largest = None
    smallest = None
    first = None
    for k in range(lo, hi):
        kind, value = items[k]
        if kind == 'x':
            first = (value, k)
            break
        total += value
        if largest is None or total > largest:
            largest = total
        if smallest is None or total < smallest:
            smallest = total
    if largest is None:
        largest = smallest = 0
    return total, largest, smallest, first


def combine(items, start, chunks):
    """The combine on the calling thread, in chunk order, starting from B = start."""
    base = start
    for lo, hi in chunks:
        total, largest, smallest, first = chunk_stats(items, lo, hi)
        if base + largest > INT64_MAX or base + smallest < INT64_MIN:
            return seq_from(items, lo, hi, base)
        if first is not None:
            return (first[0], first[1], base + total)
        base += total
    return (None, len(items), base)


def parallel_reduce(items, start, prefix, chunks):
    """The probe prefix sequentially on the calling thread, then the chunked wide phase."""
    early = seq_from(items, 0, prefix, start)
    kind, stopped, base = early
    if kind is not None or stopped != prefix:
        return early
    if len(items) - prefix < 2:
        return seq_from(items, prefix, len(items), base)
    return combine(items, base, chunks)


def parallel_map_sum(items, chunks):
    """The map on chunks (lowest failing chunk wins), then a left-to-right sum of the results."""
    for lo, hi in chunks:
        for k in range(lo, hi):
            if items[k][0] == 'x':
                return (items[k][1], k, 0)
    return seq_from(items, 0, len(items), 0)


# -- case generation ----------------------------------------------------------------------------
BIG = 1 << 62
NEAR = (0, 1, -1, BIG, -BIG, BIG - 1, -BIG - 1, INT64_MAX, INT64_MIN,
        INT64_MAX - 1, INT64_MIN + 1, 7, -7, 1000000007, -1000000007)


def rand_value(rng):
    pick = rng.random()
    if pick < 0.72:
        return rng.choice(NEAR)
    if pick < 0.86:
        return rng.randint(-(1 << 62), 1 << 62)
    return rng.choice((INT64_MAX, INT64_MIN, BIG, -BIG))


def make_items(rng, n, allow_exc=True):
    items = [('v', rand_value(rng)) for _ in range(n)]
    # The two patterns the brief names, so they are always represented among the cases.
    pattern = rng.random()
    if n >= 3 and pattern < 0.30:
        items[:3] = [('v', BIG), ('v', BIG), ('v', -BIG)]
    elif n >= 2 and pattern < 0.60:
        items[:2] = [('v', -BIG), ('v', BIG)]
    if allow_exc and n and rng.random() < 0.55:
        k = rng.randrange(n)
        items[k] = ('x', rng.choice(('ZeroDivisionError', 'ValueError', 'IndexError')))
    return items


def rand_chunks(rng, lo, hi):
    n = hi - lo
    if n <= 0:
        return []
    style = rng.randrange(5)
    if style == 0:
        return [(lo, hi)]
    if style == 1:
        return [(k, k + 1) for k in range(lo, hi)]
    cuts = sorted(rng.sample(range(lo + 1, hi), rng.randrange(min(n, 8))) if n > 1 else [])
    bounds = [lo] + cuts + [hi]
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]


def rand_reduce_case(rng):
    n = rng.choice((0, 1, 2, 3, 4, 5, 8, 13, 31, 64, 129))
    items = make_items(rng, n)
    start = rng.choice((0, 1, -1, BIG, -BIG, INT64_MAX, INT64_MIN, rng.choice(NEAR)))
    prefix = rng.randrange(n + 1)
    chunks = rand_chunks(rng, prefix, n)
    return items, start, prefix, chunks


def rand_map_case(rng):
    n = rng.choice((0, 1, 2, 3, 4, 5, 8, 13, 31, 64))
    items = make_items(rng, n)
    chunks = rand_chunks(rng, 0, n)
    return items, chunks


def main():
    cases = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    rng = random.Random(20261105)
    reduce_cases = cases * 7 // 10
    map_cases = cases - reduce_cases
    bad = []
    for _ in range(reduce_cases):
        items, start, prefix, chunks = rand_reduce_case(rng)
        want = sequential(items, start)
        got = parallel_reduce(items, start, prefix, chunks)
        if want != got:
            bad.append(('reduce', items, start, prefix, chunks, want, got))
    for _ in range(map_cases):
        items, chunks = rand_map_case(rng)
        want = sequential_map_sum(items)
        got = parallel_map_sum(items, chunks)
        if want != got:
            bad.append(('map', items, chunks, want, got))
    print('cases: %d (%d reduce, %d map)' % (cases, reduce_cases, map_cases))
    for row in bad[:5]:
        print('DIFF', row)
    print('differences: %d' % len(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
