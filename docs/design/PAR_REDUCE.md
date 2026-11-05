# PAR_REDUCE: the exact shared-int reduction in a parallel region (D1 option c)

Design note for fbred1.  **No compiler or runtime change is made here**; this file, a Python
reference model and 16 probes are the whole deliverable.  fbred2 builds the lowering and measures
the cost, fbred3 turns the probes from refused into matching their sequential twins.

Owner decision D1 chose (a) keep refusing the shape for races2 and asked for (c) as its own job
(`lab/race/owner_decisions.md`, "D1").  The shapes are a read-modify-write of one int by every
iteration of a parallel region; a per-thread partial sum alone is not exact, because AIL stops at
the first int64 overflow in iteration order while CPython prints the exact big int, and the
overflow can fall in any chunk.

## Shape, v1

In a parallel body -- `par_range`, the `_ail_pmap` loop that `ThreadPoolExecutor(k).map` and
`Pool(k).map` lower to, and the `Thread`-k loop -- a statement

```
acc += e        acc -= e
```

where

* `acc` is an int local of the enclosing function, assigned before the loop;
* `e` is an int expression that the ownership proof already accepts (scalars, `xs[i]`, and calls
  of top-level int/float functions that do nothing but compute);
* `acc` is not read or written anywhere else in the body.

Several accumulators are allowed (`p09` has `acc += i` and `neg -= i`).  The rest of the body
still writes only its own locals.  A body that also writes `xs[i]` **stays refused in v1**: if an
overflow is caught by a `try` (here or in any caller), the sequential loop stops at the overflow,
and writes made by later iterations would already be visible through `xs`.  That is observable and
cannot be repaired by the combine, so it is out of scope rather than approximated.

Also

```
acc = sum(ex.map(f, xs))
acc = sum(pool.map(f, xs))
```

Here the order differs: the map finishes first, so the first exception from `f` in iteration order
wins over any overflow, and only then does the sum stop at its first overflowing prefix
(`p10` is the probe: `f` raises at 3 while the sum would overflow at 1, and the exception wins).

## Per-chunk data

The runtime fixes a contiguous index range for each chunk `c` (the existing block cut,
`n / (threads * 8)` iterations, dealt out by the atomic counter; the probe prefix is the part the
calling thread already ran before the wide phase).  Each chunk produces

* `S_c` -- the partial sum of its completed iterations;
* `M_c` -- the largest prefix sum over prefixes of length 1 and more;
* `m_c` -- the smallest such prefix;
* the chunk's first exception.

`S_c`, `M_c`, `m_c` are kept in `__int128` (the C type) and cover only the iterations before the
chunk's first exception, because a chunk stops there (`fail_block` semantics of `ail_par_work`).
An empty prefix list is stored as `(0, 0, 0)`; it cannot trigger the overflow test.

## The combine

The combine runs on the calling thread, in chunk order, starting from `B`, the value of `acc` before
the loop:

```
B = acc_before
for each chunk c in increasing index order:
    if B + M_c > INT64_MAX or B + m_c < INT64_MIN:
        # the sequential loop stops inside c
        re-run c alone, sequentially, from B, with the ordinary checked int64 add
        return what that run returns          # same iteration, same OverflowError text
    if c has an exception:
        raise it                               # with acc = B + S_c up to the exception
    B += S_c
acc = B
```

The exception branch carries `B + S_c`, the last prefix that fitted before the exception; that is
the value `acc` has in a sequential run at the same point.

## Why it is exact

* `B` at the start of chunk `c` is exactly the value the sequential loop holds after all iterations
  before `c`, by induction over chunks: a chunk that neither stops nor raises adds its whole `S_c`,
  and integer addition is exact when no prefix leaves int64.
* The sequential loop leaves int64 inside `c` **iff** some prefix of `c`, added to `B`, leaves
  int64; that happens **iff** the largest or the smallest prefix does.  So the test is complete
  and sound, and the re-run stops at the very iteration the sequential loop stops at.
* `__int128` cannot overflow: a chunk has at most `2^63` terms of magnitude at most `2^63`, so a
  partial sum or prefix has magnitude at most `2^126`, far inside `2^127`.
* Chunks are contiguous and ordered, so "the first exception in chunk order" is "the first
  exception in iteration order" -- the lowest failing block that `ail_par_go_wide` records.
* The probe prefix is run with the same checked add on the calling thread, so it is exactly the
  sequential prefix; where it ends does not matter, because the wide phase starts from the value
  it leaves.
* For `sum(map)`, the map raises before any summing; after it completes, the sum is the ordinary
  left-to-right checked sum, whose first overflow is the sequential one.  This is already what the
  typed path does today (probes p10, p14, p15 build and match their twins).

## The re-run

The re-run is possible because `e` may call only pure int/float functions that the ownership proof
already requires: no I/O, no allocation, no observable side effect, no other shared write.  Running
one chunk twice therefore has no effect beyond recomputing the same values.  The cost is bounded by
one chunk: the combine stops at the first chunk whose test fires, and every chunk before it is
already decided.

`acc` after a caught overflow is the last prefix that fitted, exactly as in the sequential loop.
The loop variable after the loop behaves as `parallel.py` makes it behave today (it is private to
the body and a read after the loop is refused); if a read after the loop is not supported today, it
stays refused.

One measured caveat for fbred2.  In today's default build, an int64 overflow in ordinary
sequential code is a loud stop (`ail_die`), not a catchable exception -- `try` around a plain
`range` loop prints nothing (`p08`'s twin).  The parallel runtime routes a worker's trap to the
calling thread and re-raises it as a catchable `OverflowError`, so a `try` around the parallel
loop can catch the reduction's stop and see `acc`.  That is a superset of the sequential behaviour
(same kind, same message, same iteration, same accumulator) and is what `p08` records, but it is a
deliberate difference in catchability and should get a DIFFERENCES row when it is built.
`p08` is also currently refused by a second, independent rule ("parallel for cannot be inside
try"), which fbred2/fbred3 must lift for that spelling.

## The probe prefix

`ail_par_run` runs a doubling probe prefix on the calling thread before `ail_par_go_wide`.  For
this reduction that prefix adds into `acc` sequentially with the checked add; the wide phase starts
from the `B` it leaves.  Nothing in the proof depends on its length, which is timing-dependent; the
model randomises it.

## Cost

Per iteration: one 128-bit add and two compare-and-moves (update `S`, `M`, `m`) in the worker, plus
the existing checked add in the prefix.  The combine is `O(chunks)`.  Target for fbred2: at most
1.15x the sequential loop's instructions at `AIL_THREADS=1`.

## Reference model

`python3 lab/race/reduce/model.py` (200,000 cases, seed 20261105):

```
cases: 200000 (140000 reduce, 60000 map)
differences: 0
```

The model compares the chunked combine against a sequential simulation of the same item list on
(exception kind or None, the iteration where the run stops, `acc` after the run).  Cases include
chunkings of length 1 and one chunk, values at 0, +-2^62, +-2^63 and INT64_MIN/MAX, the patterns
`+big, +big, -big` (stops) and `-big, +big` (fits), exceptions before and after the overflow point,
several start values and every probe-prefix split.  Two mutations show the test has teeth: dropping
the `M_c`/`m_c` test gives 1,468 differences in 20,000 cases; dropping the partial sum from the
exception carry gives 302.

## Probes

16 parallel probes and their sequential twins are in `lab/race/reduce/`; `EXPECTED.md` holds the
twin's measured output, the CPython comparison and today's build status.  The twin is the expected
output by construction: `range` replaces `par_range`, and the `sum(map)` twins run a sequential map
pass before the sum.  The try probe is the one exception, explained there.

## How many programs this moves today

Measured on 2026-11-05 (branch `job-fbred1-11060646`).  "Refused for this reason" means the compile
failed with the shared-int refusal (`'acc' is read before the body assigns it. Each iteration
starts with fresh locals ...`) or with a refusal of the `sum(...map...)` spelling.

| tree | programs | refused for a shared int `+=` in a parallel body | refused for `sum(...map...)` over a parallel map |
|---|---|---|---|
| `lab/race/` before this job (14 racy + 17 safe + 3 hybrid pairs) | 34 | 0 | 0 |
| `lab/race/reduce/` (new, 16 parallel probes) | 16 | 12 | 0 (3 build and match; 1 needs the try rule) |
| `lab/corpus/programs`, first 500 (219 present) | 219 | 0 | 0 |

`lab/race/` has no `par_range` shared accumulator: `grep -rn par_range lab/race` finds only a
docstring in `racy/neighbour.py` and a note string in `run.py`, and the racy shared-int probes use
`threading` globals, which build on the general path under the lock (`lab/race/RESULTS.md`).
None of the 219 corpus programs imports `threading`, `concurrent.futures` or `multiprocessing`, so
no corpus program can use either shape.

So **fbred3 moves 12 of the 16 new probe programs** (the other three already build and match); the
existing `lab/race/` probes and the corpus move 0.

The second shape is worth stating plainly: `acc = sum(ex.map(f, xs))` and `sum(pool.map(f, xs))`
at top level are **already accepted** on the typed parallel path and already exact for overflow
(p10, p14, p15), so their refused count is 0 and fbred3 changes nothing there.  The only refused
`sum(map)` spelling found is a map inside a parallel body, refused as
`_ail_pmap1() is called in a parallel body, so it must return int or float`; that is a different
rule (a container-returning call in a body) and is not part of shape v1.
