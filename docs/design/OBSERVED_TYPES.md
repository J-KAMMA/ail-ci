# Observed types: guarded native code from run-time kinds

Status: probe + recorder (job obs1, 2026-11-09). No codegen or default-build change. Recorder:
`AIL_CURRENT/ail_observe.py` (test `test_ail_observe.py`). Probe: `lab/wedge/observe_probe.py`,
tables `lab/wedge/observe_report.py`, data `lab/wedge/observe_probe.json`, boundary cost
`lab/wedge/guard_cost.py` / `guard_cost.json`.

The rule does not change: **never a silent difference from CPython.** A profile is a hint, never a
proof. Every native call is protected by checks; a failed check runs the original function.

## 1. What was measured (lab/wedge, 15 modules, 97 top-level functions)

Four hybrid builds per module with the unchanged `ail build --cpython`: `hand` (as committed),
`hand+obs` (observed kinds fill missing annotations), `bare` (all annotations stripped), `bare+obs`
(stripped, then only observed kinds written). Speed is user-space instructions (`tools/icount.c`);
wall medians of 5 are in the JSON but are not used: on this laptop the CPython column of
`float_loops` ranged 7.6-12.0 s while its instruction count equals the hybrid's to 0.2%.

| config | native funcs | time share | corpus instructions vs CPython |
| --- | ---: | ---: | ---: |
| hand | 29 / 97 (29.9%) | 7.4% | 0.969 |
| hand+obs | 29 / 97 (29.9%) | 7.4% | 0.969 |
| bare | 0 / 97 | 0% | 1.001 |
| bare+obs | 29 / 97 (29.9%) | 7.4% | 0.969 |

* **Observation replaces annotations exactly**: untyped code recovers the hand-typed selection,
  function for function. It adds nothing on top of complete hand annotations.
* **Correctness**: 60 hybrid builds, all byte-identical (stdout, exit, last stderr line) to the
  committed oracle and to live CPython; the annotated sources and the recorder run are identical too.
* **Price**: native share 7.4% (6.0 of 80.6 s sampled self time) gives an Amdahl bound of 1.080x;
  achieved 1/0.969 = 1.032x, i.e. 42% of the bound. Best modules: `json_parse` 0.883,
  `rolling_stats` 0.887, `dataframe_group` 0.930. `field_valid` has 54.1% native share (bound
  2.18x) and gets 0.961 (boundary cost, section 3); `tokenizer` has 9.4% and gets 1.000 (load
  defect, next bullet).
* **Defect: 9 of the 29 "accelerated" functions never run natively.** Every unit that indexes
  (wedge2's trap path) declares its trap flag `static __thread int <unit>__hybrid_trap` while the
  wrapper reads it as `extern`, so the `.so` fails to load (`undefined symbol`), the preamble
  catches the ImportError and the whole module runs on CPython while `build.json` still lists the
  functions. Affected here: `edit_dist` (3), `matrix` (5), `tokenizer` (1). Minimal repro: a module
  holding only `def first(xs: list[int]) -> int: return xs[0]`. Output stays correct (it is all
  CPython), so the oracle check cannot see it. Really native today: 20 / 97, 6.7% share. Dropping
  the `static` (one word in `_trap_patch`; measured locally, not committed) loads all 9, keeps all
  outputs byte-identical, and moves `tokenizer` 1.000 -> 0.768, `edit_dist` 1.000 -> 0.964 and the
  corpus 0.969 -> 0.957 (1.045x, 56% of the 1.080x bound); data in
  `lab/wedge/observe_probe_trapfix.json`.
* **Polymorphism is not the blocker.** No function saw two scalar kinds. The only multi-kind slots
  are `ast_lint`'s recursive tuple tree (one container type, varying element shapes: 9.6%).

Remaining refusals, `bare+obs`, by sampled self time:

| reason | share | funcs |
| --- | ---: | ---: |
| not a top-level function (methods; `Tree._depth` 9.7M calls) | 34.7% | 20 |
| unresolved-return: list returns 13.5% (`mat_mul` alone 6.4%); `bool` via `return a and b` 8.1% | 21.6% | 16 |
| observed shape varies: tuple (`ast_lint`) | 9.6% | 7 |
| a call can raise | 5.7% | 7 |
| param kind not tracked: nested list / bytes / list[str] | 5.1 / 2.8 / 1.9% | 5 / 6 / 4 |
| to_c refused / division can raise / list[float] ABI defect / list param mutated | 3.4 / 2.9 / 2.8 / 1.2% | 5 / 4 / 7 / 3 |

The 5 `bool`-returning functions were observed monomorphic (`bool`, 1072-1136 samples each), but
the hybrid ignores return annotations: `pymix` infers returns itself. Seeding is a hybrid-only hook.

Recorder overhead (instructions / CPython): default (exact call counts) geomean 1.43x, max 6.0x
(`tree_build`, 29M calls), corpus total 1.58x; `--fast` (counting stops after the sample budget,
calls become lower bounds) geomean 1.04x, max 1.06x; cProfile for reference 1.92x, max 3.66x.
Self time comes from a 1 ms SIGPROF sampler; it is biased toward callers for very short
functions (`json_parse` saved 11.7% instructions with a 3.3% sampled share), so shares rank, they
do not add up exactly.

## 2. Guard design

**Scalars.** Exact-type checks in C at the entry: `PyLong_CheckExact` plus an int64 range check,
`PyFloat_CheckExact`, `PyBool_Check` kept distinct from int, `PyUnicode_CheckExact`. The checks
run before any native work, so a failure has no side effect to undo: call the original function
object with the same arguments. Today this is done by two Python frames
(`_ail_hybrid_call` -> `_ail_hybrid_invoke`) plus the C type checks; measured cost below.

**Containers.** Three options, measured or argued:

1. *Check every element at entry* (today: `list[int]` is copied into a C buffer, each element
   checked). Measured 6.2 ns per element against CPython's 18-22 ns per element for a sum loop,
   so `total(xs)` is capped at 3.4x (0.29-0.36 of CPython at 1k-100k elements). Correct, but
   O(n) per call even when the body reads one element.
2. *Sampled check at entry.* Unsafe alone: a list can hold a `str` between samples (the recorder's
   own test shows the sampler missing one). Usable only as a selection hint.
3. *Check at the point of element use.* Native code reads `PyList_GET_ITEM` directly (no copy) and
   checks each loaded item's type where it is used (one compare, ~1 ns). On a mismatch the call
   is restarted in CPython. Restart is correct only for a body with no visible side effect before
   the check (read-only: sum, count, max, search, hash) -- the rule the hybrid already applies to
   `IndexError` (trap, then re-run the original). The GIL is held and native code never calls back
   into Python, so the list cannot change under the native loop.

Recommendation: (3) for read-only bodies, (1) for the rest; never (2) as a guard. Lists created by
native code (an AIL typed container handed back to Python) need no check, but at the CPython
boundary that case is rare.

**Deopt.** The unit is the whole call: a failed guard or a trap re-runs the original function
from the start (measured 1.24 us for the int64-overflow fallback vs 78 ns in CPython). Each native
wrapper keeps a failure counter; after 64 calls with more than 1/16 failing it rebinds the name to
the original function, so a mis-profiled function stops paying guard plus fallback.

**What invalidates a profile.** Profiles are keyed by file SHA-256, qualname and Python minor
version; any change discards the entry. A run-time failure rate above the threshold marks the
function for re-observation. Since every value is checked, a stale profile costs speed, never
correctness.

## 3. Cost model (measured, `guard_cost.py`, in-process medians)

| case | CPython | hybrid |
| --- | ---: | ---: |
| `add1(n)` (guard + boundary, no work) | 45 ns | 406 ns |
| `work(10)` / `work(100)` / `work(1000)` | 470 / 6,001 / 79,369 ns | 570 / 914 / 2,619 ns |
| `total(xs)`, 1,000 / 100,000 ints | 18.3 us / 2.25 ms | 6.7 us / 0.65 ms |

Per call: gain = T_py - T_native - G, with G ~ 360 ns today. Break-even is ~10 loop iterations
(`work(10)` is 1.21x slower, `work(100)` 6.6x faster). This explains `field_valid`: its 4 native
functions take 2.8M calls of a few hundred ns each, so ~1.0 s of boundary (2.8M x 360 ns) eats
most of the saving. (`tokenizer` and `edit_dist` missed for the load defect in section 1, not for
the boundary.) A C entry with in-C scalar guards (vectorcall, no Python frame) should bring G
to tens of ns; that is the estimate to verify, not a measurement.

## 4. Step 3 split into tasks of at most 2 hours, ranked by measured gain

0. **Load the trap units** (minutes): drop `static` from the trap flag in `_trap_patch`, and make
   the build check that the `.so` it wrote actually imports (fail the build or empty
   `accelerated` otherwise). Measured: corpus 0.969 -> 0.957, 9 functions really native. Guard: a
   `test_ail_cpython_hybrid` case that imports the extension of an indexing function.
1. **C entry wrapper** (`ail_cpython_hybrid._wrapper_source`): a vectorcall function per native
   unit that does the scalar checks in C and calls the stored original on failure, replacing
   `_ail_hybrid_call`/`_ail_hybrid_invoke`. Gain: the 7.4% share is realised at 56% of its bound
   even after task 0; `field_valid` (54.1% share, bound 2.18x, now 1.04x) is boundary-bound.
   Guard: `test_ail_cpython_hybrid` + guard_cost `add1` below 100 ns.
2. **Observed return-kind seed** (hybrid analysis hook only): seed `pymix` return kinds from a
   scalar return annotation written by `ail_observe annotate`. 5 functions, 8.1% share
   (`is_simple_email`, `is_ident_char`, ...). Worth it only after task 1: all 5 are tiny
   (1-2M calls each).
3. **List return ABI** (`list[int]`/`list[float]`, wedge1 W2) plus the `list[float]` parameter
   spelling fix: list returns 13.5% (`mat_mul` 6.4%, `window_sums` 2.7%), `list[float]` ABI 2.8%.
4. **Methods, step a**: a method whose `self` is only read for scalar attributes, guarded by
   `type(self) is C` plus an attribute check. Ceiling 34.7% (largest), but needs a short design
   first; split further before queueing.
5. **Element-use container guard** (option 3) for read-only bodies: nested list 5.1%,
   `bytes` 2.8%, `list[str]` 1.9%; also removes the O(n) entry copy from task 3's inputs.

Even with every task done, the corpus figures above say how far this route goes: a guarded native
build only reaches the functions it compiles. Re-run `observe_probe.py --icount` after each task
and report share, bound and achieved fraction.
