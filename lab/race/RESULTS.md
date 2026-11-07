# Race probe suite: measured after races2

`python3 lab/race/run.py`. CPython 3.12.3; the default AIL build and `AIL_UNIFIED_FORCE=1`; hybrid probes built with `ail build --cpython`; `AIL_THREADS` 1, 2, 4, 16, three runs each.

## After

| count | value |
|---|---|
| silent races | **0** |
| safe matched | **17** of 18 |
| safe GIL-free | **17** of 18 |

Baseline when this job started (races1): silent races 0, safe matched 11 of 12, safe GIL-free 11 of 12. The five new safe probes (`map_range`, `map_range_start`, `map_enumerate`, `futures_after_with`, `submit_after_with`) all build on the typed parallel path. The one unmatched safe probe is `int_beyond_int64`, which stops loudly at the int64 boundary (its own note says that is allowed) and is the expected failure in `test_ail_race_probes`.

No racy probe was a silent race: every one was refused by name or built on the general path under the lock, printed CPython's output, and passed TSan where it had a typed parallel build.

## Per-probe table

| probe | kind | default path | default match | force path | force match | hybrid | TSan |
|---|---|---|---|---|---|---|---|
| racy/float_cell.py | racy | general | yes | general (forced) | yes | - | - |
| racy/global_add.py | racy | general | yes | general (forced) | yes | - | - |
| racy/map_writes_global.py | racy | general | yes | general (forced) | yes | - | - |
| racy/max_cell.py | racy | general | yes | general (forced) | yes | - | - |
| racy/mod_two.py | racy | general | yes | general (forced) | yes | - | - |
| racy/neighbour.py | racy | general | yes | general (forced) | yes | - | - |
| racy/nested_writes_outer.py | racy | general | yes | general (forced) | yes | - | - |
| racy/resize_while_index.py | racy | general | yes | general (forced) | yes | - | - |
| racy/same_list_twice.py | racy | general | yes | general (forced) | yes | - | - |
| racy/shared_dict.py | racy | general | yes | general (forced) | yes | - | - |
| racy/submit_shared.py | racy | general | yes | general (forced) | yes | - | - |
| racy/two_names.py | racy | general | yes | general (forced) | yes | - | - |
| racy/write_slot0.py | racy | general | yes | general (forced) | yes | - | - |
| safe/exception_first.py | safe | general | yes | general (forced) | yes | - | - |
| safe/futures_after_with.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/int_beyond_int64.py | safe | typed parallel | no | general (forced) | no | - | exit 1: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| safe/large_map.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/map_enumerate.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/map_float.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/map_int.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/map_range.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/map_range_start.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/more_results.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/one_worker.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/partial_sums.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/pool_map.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/shared_append.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/sixteen_on_three.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/submit_after_with.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/thread_blocks.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| safe/thread_k.py | safe | typed parallel | yes | general (forced) | yes | - | clean |
| hybrid/hybrid_bytearray.py | hybrid | refused | no | refused | no | accelerated tagged; extension loaded; match yes | - |
| hybrid/hybrid_ints.py | hybrid | typed parallel | yes | general (forced) | yes | accelerated combine; extension loaded; match yes | - |
| hybrid/hybrid_list_append.py | hybrid | general | yes | general (forced) | yes | accelerated total; extension loaded; match yes | - |

## Notes

- Paths: `typed parallel` is the lock-free `_ail_par_range` build (its C holds `ail_par_run`); `general` is the `note: ... built on the general path ...` build under one lock; `refused` is a compile-time refusal by name.
- `force` is `AIL_UNIFIED_FORCE=1`, which the job asks for as the second build. It forces the general path for every program, so it is a soundness check rather than a second typed build.
- A racy probe is counted silent if its default build is typed parallel, if any run differs from CPython, or if ThreadSanitizer reports on it.
- `safe GIL-free` counts safe probes whose default build is the typed parallel path; it is the count later steps raise.
- Each hybrid row is a helper module `<name>.py` built with `python3 -B AIL_CURRENT/ail_chatgpt.py build --cpython lab/race/hybrid/<name>.py -o <out>`, plus the threaded CPython runner `<name>_run.py`. `run.py` copies the runner to a directory that does not hold the helper, so `import <name>` reaches the generated wrapper and its native module; the `extension loaded` column proves that. The runner's stdout and exit status are compared with CPython.
- The default and forced columns also compile and run the same runner copy in the ordinary AIL builds, so every row has both. Two hybrid runners build there; `hybrid_bytearray_run.py` is refused by both with `general path: join() called with too many positional arguments` (a `bytearray` subscript in a thread body), so that row's match is measured from the hybrid build, where `checksum` stays in CPython and only `tagged` is accelerated.

### Refusals (by name)

- `hybrid/hybrid_bytearray.py` (default): `lab/race/hybrid/hybrid_bytearray_run.py:3:1: not in the subset: threading, queue and concurrent.futures are built on the general path only (one interpreter lock, CPython's GIL semantics); this program is compiled there (the general path could not build this program either); general path: join() called with too many positional arguments`
- `hybrid/hybrid_bytearray.py` (force): `not in the subset: join() called with too many positional arguments`

Elapsed: 210 s. 34 rows (13 racy, 18 safe, 3 hybrid).

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
