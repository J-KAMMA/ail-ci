## Owner decisions (2026-11-05)

The owner answered はい to these on 2026-11-05; they replace "stop and report" for D1-D4. Only D4 is
built here; D2 and D3 are follow-up jobs.

### D1. `total += f(i)` on a shared int in a parallel body

Chosen: **(a) keep refusing it**. The loop runs under the lock (or the user writes `out[k]` partials).
The exact semantics (c) are wanted later as their own job and are not built here.
Why it is not just allowed: sequential AIL stops with OverflowError at the first prefix sum beyond
int64, while CPython yields the exact big int. Per-thread partial sums can overflow where the
sequential loop does not, and the other way round.

- Probes: `racy/global_add.py`, `racy/map_writes_global.py`, `racy/max_cell.py` (all still refused
  by name and run under the lock); `safe/int_beyond_int64.py` is the int64 boundary itself.
- Costs: (a) no new code, a lexical parallel body keeps its scalar locals only and shares through
  `out[k]`; (b) checked int64 partials would stop loudly where the sequential loop would not
  (a DIFFERENCES entry); (c) exact semantics needs each chunk's sum plus its highest and lowest
  prefix in 128-bit ints so the combine knows whether, and in which chunk, the sequential loop would
  have stopped -- the same result as sequential, more code in the PAR runtime.

### D2. `total += x` on a shared float

Chosen: **(b) allow it only behind an explicit opt-in**, with one fixed chunking that is the same at
every thread count. Deterministic, but not CPython's left-to-right last bits; the typed-array decision
of 2026-10-30 chose a fixed sum order there too. **Not built in this job.**

- Probes: `racy/float_cell.py` (today refused by name, runs under the lock). A new probe would
  exercise the opt-in spelling.
- Costs: (a) today's behaviour, no code; (b) a fixed chunking plus an opt-in flag, and a DIFFERENCES
  entry for the last bits; (c) allowing it by default would silently change float sums for every
  existing program.

### D3. A parallel body appends to, or otherwise writes, a shared list

Chosen: **(c) per-chunk buffers concatenated in iteration order**, so the result equals the sequential
one for `map`-like shapes. Not for free-running `Thread`s, whose CPython order depends on the
schedule. **Not built in this job.** Today the lock-free lowering is refused and the program runs
under the lock with a note.

- Probes: `racy/shared_append.py`, `racy/resize_while_index.py`. Lowering (c) would move the first
  from `racy/` to `safe/` (it then matches CPython deterministically); `resize_while_index.py` would
  stay racy because its append and its `out[k]` writes interleave.
- Costs: (c) one buffer per chunk in the PAR runtime, a combine step that concatenates in iteration
  order, and a compile-time rule that only pure `append` (not `pop`, `insert` or a second name) is
  buffered; (a) today's note; (b) `--strict` errors where a note is printed otherwise.

### D4. A hybrid-mode native call that takes a container while other CPython threads run

Chosen: **(a) keep the GIL for it**, the provisional safe default. **Built in this job.**
`ail_cpython_hybrid.py` now emits the native call without `Py_BEGIN_ALLOW_THREADS` when any parameter
is `list[int]` or `list[float]`; calls whose parameters are only int, float, bool or str still release
it. A function cannot index (so it cannot read a module-level container) and a mutated list parameter
already stays in CPython, so lists are the only container an accelerated call sees.

- Probes: `hybrid/hybrid_ints.py` (ints only, still GIL-free), `hybrid/hybrid_list_append.py`
  (`total(list[int])` now holds the GIL during the call), `hybrid/hybrid_bytearray.py` (a `bytearray`
  parameter stays in CPython), plus `test_ail_cpython_hybrid.test_container_calls_keep_the_gil`.
- Costs: (a) list-taking calls lose the overlap with other threads; (b) copying the container before
  releasing keeps the overlap but costs memory and a copy per call; (c) not accelerating such a
  function at all in a program that imports `threading` is safer still and loses more speed.

### Follow-up jobs this lane did not build

- D2's fixed-order float sum behind an opt-in (needs a spelling and a DIFFERENCES entry).
- D3's per-chunk append buffers in `parallel.py`/`cruntime.py` (and moving `racy/shared_append.py`
  to `safe/`).
- D1(c)'s exact shared-int reduction (a new job, as the owner asked).
- `futs[0].result()` (indexing a futures list outside a loop) is still refused by name; it needs an
  index-bounds rule in `typedpar.rewrite_uses`, not a semantics decision.
