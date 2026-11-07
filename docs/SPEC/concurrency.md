# Concurrency

AIL has two concurrency stories: the general path keeps CPython's shared-everything threads under
one lock, and the typed path runs a small set of fork-join shapes without a lock when it can prove
the workers cannot interfere. This chapter fixes both, and the owner decisions D1-D5 that bound
them.

## CO1 — The general path: one lock, CPython's answers

**Rule.** `threading`, `queue` and `concurrent.futures` are built on the general path with one
interpreter lock. A program that uses them prints the general-path note and runs about 20x slower
than a typed program, but has CPython's semantics: a `Lock`, a `Condition`, an `Event`, a queue
and a futures executor all behave as CPython's do, and a data race has CPython's possible answers.

```python
import threading

total = 0
lock = threading.Lock()

def add():
    global total
    with lock:
        total += 1

ts = [threading.Thread(target=add) for _ in range(4)]
for t in ts:
    t.start()
for t in ts:
    t.join()
print(total)                  # 4
```

**CPython.** The same, with the real GIL.

**Status.** implemented (general path).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A38; [`docs/LIMITATIONS.md`](../LIMITATIONS.md)
14; `test_ail_threads`.

## CO2 — The typed path: recognised fork-join shapes only

**Rule.** The typed path parallelises only these shapes:

* `ThreadPoolExecutor.map(f, range(...))` or `map(f, xs)` consumed in the block;
* `multiprocessing.Pool.map(f, xs)` (a thread pool in AIL) consumed in the block;
* a group of `submit(f, ...)` futures created and read in one block;
* a list of `Thread`s started and joined in one block;
* a `parallel for` over `par_range` / `_ail_par_range`.

A body outside this set runs under the lock (CO1) or is refused by name. A `submit` future that
escapes the block is refused.

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(4) as pool:
    out = list(pool.map(f, range(100)))   # parallel; results in input order
```

**CPython.** Executes the same shapes with the GIL and no parallel speed-up.

**Status.** implemented for the listed shapes; the fallback is the lock.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A66, A67, A74, A75;
[`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md).

## CO3 — D1: a shared int read-modify-write is refused

**Rule.** A parallel body that reads and writes the same integer (`total += x`, `table[k] += v`)
is refused and the loop runs under the lock. The supported way to reduce is a per-iteration
partial written to a disjoint element (`out[k] = ...`) and a sequential combine, or the later
exact reduction of `PAR_REDUCE.md`. A parallel body may not rely on the order in which two
workers add.

```python
out = [0] * n
for k in par_range(n):
    out[k] = f(k)             # disjoint write: parallel
total = sum(out)              # sequential combine
```

**CPython.** Under the GIL a `+=` is not atomic but usually appears to work; AIL will not guess.

**Status.** refused today; exact reduction planned.

**Proof.** [`lab/race/owner_decisions.md`](../../lab/race/owner_decisions.md) D1;
[`docs/design/PAR_REDUCE.md`](../design/PAR_REDUCE.md); `lab/race/`.

## CO4 — D2: a shared float accumulator needs an explicit opt-in

**Rule.** A shared float accumulator in a parallel body is allowed only when the program opts in
to the fixed chunking (a named annotation or call, per the design). The chunking is the same at
every thread count, so the result is reproducible. D2 is not built on this tree.

```python
total = 0.0
for k in par_range(n):        # refused today: a shared float accumulator without the D2 opt-in
    total += xs[k]
```

**CPython.** Adds in scheduling order, so the result can differ between runs.

**Status.** planned (not built).

**Proof.** [`lab/race/owner_decisions.md`](../../lab/race/owner_decisions.md) D2;
[`docs/design/PAR_REDUCE.md`](../design/PAR_REDUCE.md).

## CO5 — D3: appending to a shared list from a parallel body

**Rule.** A parallel body that appends to a shared list is refused today. The accepted future
lowering gives each chunk its own ordered buffer and concatenates the buffers in iteration order,
so the list matches the sequential result. A program that needs it now writes `out[k] = value`
and builds the list afterwards.

```python
out = [None] * n
for k in par_range(n):
    out[k] = work(k)
xs = [out[k] for k in range(n)]
```

**CPython.** Appends under the GIL in scheduling order, which is not the loop order.

**Status.** refused today; ordered-buffer lowering planned.

**Proof.** [`lab/race/owner_decisions.md`](../../lab/race/owner_decisions.md) D3.

## CO6 — D4: a native call with a container keeps the lock

**Rule.** In hybrid mode (MF7) a native function that takes a container keeps the GIL for the
whole call; a native function with only scalar arguments releases it. So a native call cannot
race a Python thread through a borrowed buffer unless the program itself shares a mutable global,
which the typed path does not.

```python
# f(xs: list[int], k: int) -> int  : keeps the lock (takes a container)
# g(k: int) -> int                 : may release the lock (scalars only)
```

**CPython.** One GIL for everything.

**Status.** implemented (hybrid mode).

**Proof.** [`lab/race/owner_decisions.md`](../../lab/race/owner_decisions.md) D4;
[`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md) "CPython hybrid".

## CO7 — D5 / R1: a worker borrows a value only inside the block

**Rule.** A value is borrowed by a worker only for an interval the compiler knows: fork and join
are in the same block, and the borrowed value is not written by the program between them. A region
that outlives its inputs (a detached thread, a future stored in a field, a callback into C) stays
under the lock or is refused.

```python
with ThreadPoolExecutor(4) as pool:      # fork and join in one block
    out = list(pool.map(f, xs))          # xs is borrowed for the block
```

**CPython.** Keeps every object alive through the threads' references.

**Status.** implemented for the recognised shapes; the general fallback holds the lock.

**Proof.** [`docs/design/SAFETY_PROOF.md`](../design/SAFETY_PROOF.md) R1.

## CO8 — R2-R5: what a parallel body may touch

**Rule.** A parallel body may write only

* its own locals and loop variables,
* provably disjoint elements of a container: `xs[i]`, `xs[i * K + j]`, `out[k]`, where the
  indices are affine and the analysis proves no two iterations collide,

and may call only top-level `int`/`float` functions that are proven pure. It may not hold a
`str`, `bytes`, list, dict, set or object reference that outlives the body, and it may not call a
function whose effect set is unknown. Race freedom is the conjunction of R1-R5; if one fails, the
region is locked or refused.

```python
for i in par_range(n):
    out[i] = a[i] + b[i]      # disjoint affine writes, pure reads
```

**CPython.** No such checks; correctness is the programmer's.

**Status.** implemented as the proof obligation; a failed check locks or refuses.

**Proof.** [`docs/design/SAFETY_PROOF.md`](../design/SAFETY_PROOF.md) R2-R5;
[`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md) sections 1-2; `test_ail_par_*`,
`test_ail_safetynet`.

## CO9 — FFI callbacks and threads

**Rule.** An FFI callback declared `threads=True` is refused. A callback invoked from another
thread, or after the C call that received it returned, aborts the program (a loud stop, not
undefined behaviour). A callback must be a module-level `def` (MF9).

```python
@extern("lib.h", threads=True)
def on_event(n: int) -> None: ...
# refused: an FFI callback may not run on a thread
```

**CPython.** A C extension may call back on any thread; the extension author is responsible.

**Status.** refused.

**Proof.** [`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md) "FFI";
[`docs/FFI.md`](../FFI.md); [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A63.
