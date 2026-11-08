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

**obs2 (tasks 0 and 1 done).** Task 0 made the trap units load and the build now imports every
`.so` it writes before build.json may list a function. Task 1 replaced the two Python frames with a
C vectorcall entry installed on the original function object (`PyFunction_SetVectorcall`, 3.12+;
older CPython keeps the Python wrapper). Guards run in C; keywords, a wrong argument count, a
guard failure, an overflow or a trap call the unaltered `_PyFunction_Vectorcall` with the same
arguments; missing arguments are filled from the current `__defaults__`; a replaced `__code__`
runs in CPython. The function object, its identity and introspection are CPython's own. Measured
(`guard_cost_obs2.json`, instructions per call from `tools/icount.c` loops): `add1` 75.8 ns vs
34.6 ns CPython (was 406 vs 45), +465 instructions per call over CPython (was ~3,800), of which
~40 ns is releasing the GIL for a scalar-only call (`total([])`, which keeps the GIL, costs 33 ns);
`work(1)` is already cheaper than CPython (1,649 vs 1,754 instructions), so break-even is below one
loop iteration (was ~10); the int64-overflow fallback costs 66 ns vs 53 ns (was 1.24 us). Profilers
(`sys.setprofile`) no longer see a call that ran natively. Corpus, `hand`, instructions vs CPython
(`obs2_hand_task0.json` -> `obs2_hand_task1.json`): 29/29 natives load; `field_valid` 0.965 ->
0.658 (share bound 0.493, 67% of it achieved), corpus 0.957 -> 0.934 (1.071x, 89% of the 1.080x
bound); every other module within icount noise (+-1.3%; `hashing`, with no native function,
moved 0.992 -> 1.005); all outputs byte-identical.

**obs3 task 3 (list results, `list[float]` parameters).** A function returning `list[int]` /
`list[float]` is native when `_list_return_proof` shows the result is a fresh local (built by
`[]`, a literal or `[c] * n`, then only appended to, indexed, stored into or measured, and returned
by every `return`) whose elements are all exact `int` (never bool) or all `float`; the exact types
come from a small optimistic pass over the body (`_Kinds`), not from `pymix`'s merged kinds. The
analysis process seeds that kind into `pymix` and builds the clone itself (the base mixed mode
does not wire list results); the wrapper reads the clone's `_out`/`_cap` buffer (a long list from
the unit's spill slot) and builds a new CPython list, holding the GIL. A `list[float]` parameter
that `to_c` passes as `ail_flist` is now called with that struct (`_unit_abi`). `len(xs)` and the
other read-only builtins no longer count as mutating a list parameter. Two holes found and closed
in the hybrid only: a reachable int64-overflow / MemoryError stop in a non-int unit now falls back
instead of exiting CPython (trap pad only where the stop is reachable, `_overflow_stop_reachable`),
and the IR's `xs[i] op= v` (checked get, then an unchecked set at the raw index: `out[-1] += 1`
corrupts the heap, **also in the default build**, left for a core fix) keeps the set checked in
hybrid clones. Measured (`obs3_task3.json`, instructions vs CPython, `hand` = `bare+obs`): natives
29 -> 44, corpus 0.934 -> 0.719 (1.39x vs CPython; 1.30x vs obs2); `matrix` 0.993 -> 0.015
(`mat_mul`), `rolling_stats` 0.880 -> 0.173, `dataframe_group` 0.921 -> 0.509, `float_loops`
1.000 -> 0.625, `bitset_bloom` 0.941 -> 0.920; every other module within noise; all 30 builds
byte-identical to the oracle and live CPython. Sampled native share 19.2% (bound 1.237x) is below
what was achieved: the 1 ms sampler under-counts these long-running loop bodies, so the share is a
ranking, not a bound, here.

**obs3 task 2 (seeded return kinds).** A scalar return annotation (hand-written, or written by
`ail_observe annotate` from the observed kinds) seeds `pymix`'s result kind only when every return
value has exactly that CPython type by the same exact-kind pass; the annotation alone is never
trusted. `return a and b` returns an operand, so it is `bool` only when both operands are exact
bools (`lies(a: int, b: int) -> bool: return a and b` stays in CPython); selection re-checks every
seeded result and every `and`/`or` result on the original source. Since the operands are proven
from guarded parameters, no run-time mismatch is possible; a non-fitting argument falls back as
before. A loop-free body now keeps the GIL (a release/re-acquire costs more than the body:
`tokenizer` went 0.767 -> 0.942 with the release, 0.715 without). Still refused: a body that
calls a user function (`count_idents`), and one that reads a module constant (`valid_len`,
`score_ok`, `csv_parse`'s `COMMA`: `to_c` refuses the name in its defs-only slice). Measured
(`obs3_task2.json`, `hand` = `bare+obs`): natives 44 -> 47, corpus 0.719 -> 0.697 (1.43x vs
CPython; sampled share 30.7%, bound 1.444x); `field_valid` 0.657 -> 0.387 (`is_simple_email`),
`tokenizer` 0.767 -> 0.715; other modules within noise; all outputs byte-identical.

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

## 5. obs4 design: methods, module constants, calls between natives

The rule stays: a native call returns exactly CPython's value, or the original runs from the
start. The new part is that a native body now depends on *names outside its arguments* (a module
constant, another function, `self`'s attributes and methods), and every such name can be rebound
at run time by code the build never saw. Each one gets a guard whose failure means "run the
original".

**Price first** (from `obs3_task2.json`: a function's sampled self-time share inside its module,
times the module's share of corpus CPython instructions; the 1 ms sampler over-weights very short
functions, which is why the "34.7%" refusal row of section 1 shrinks here):

| refusal | corpus share (instr.) | bound on the corpus figure |
| --- | ---: | --- |
| methods, read-only (`tree_build`: `_inorder`/`_height`/`_depth`, 99% of the module) | 5.7% | 0.697 -> ~0.643 (1.43x -> ~1.56x) |
| methods that store scalar fields (`json_parse` `Parser.*`, `self.pos += 1`) | 5.1% | another ~-0.05 (step b, not now) |
| module constants (`csv_parse` x4 `COMMA`, `field_valid` `valid_len`/`score_ok`) | ~7% (sampled; long loops) | most of csv_parse's 0.93 |
| calls to user functions (`count_idents`, `longest_ident`) and `ch.is*()` on a local str | ~0.5% | small; prerequisite for recursive methods |

So the order is constants + calls (cheap, and recursion through `self._depth(...)` needs the call
rule), then read-only methods. `levenshtein` (a local list's `.append`, 7.9% sampled) is a
different refusal and is not in this job.

### 5.1 Module constants

`_module_constants` already finds `NAME = <int/float/str/bool literal>` bound exactly once in the
file and never declared `global`; `to_c` refused them only because the hybrid hands it the
defs-only slice. The analysis process adds those assignments in front of the slice (`to_c` emits
`static const`), for the hybrid only. Ints must fit int64 and strs must be UTF-8 encodable.

What CPython can still do: `mod.NAME = 5` from another module, `globals()['NAME'] = ...`,
`del NAME`, or call the function before the assignment has run (NameError). Guard: the C entry
keeps, per constant, a "verified" flag. Verification looks the name up in the function's
`__globals__` and compares exact type and value (int by value, float by bit pattern, str by
`PyUnicode_Compare`, bool by identity); missing or different -> run the original. A dict watcher
(`PyDict_AddWatcher`, 3.12+) on that globals dict clears the flag of any guarded key that is
added, changed or deleted, and every flag on clear/clone/dealloc; so the per-call cost is one load
per constant. If the interpreter's 8 watcher slots are taken, every call re-verifies (one dict
lookup per name). A function whose globals are not the watched dict runs the original.

### 5.2 Calls between natives

`f` may call a top-level `g` when `g` is itself selected, the module binds `g` once (its `def`),
the call passes exactly `g`'s parameter count positionally (no keywords, no defaults used), and the
exact-kind pass (`_Kinds`, now told the callees' exact result kinds) proves each argument has the
exact kind `g`'s entry checks (`int` never a bool, `float`, `str`, a list parameter of the same
kind). Then `g`'s own selection proof holds at the call site and `to_c`, which compiles `f`'s
unit from all defs, inlines or calls `g`'s C copy. Selection runs to a fixed point; self-recursion
is assumed optimistically for `f` itself; mutual recursion and more than one recursive function in
a unit are refused (the depth accounting below needs a single recursive chain).

Guards: `g` is a guarded global like a constant: verified when `__globals__[g]` is a function
whose vectorcall is `g`'s native entry (so it is the def this unit compiled), plus a per-call
pointer compare of `g.__code__` against the codes recorded at install (`__code__` assignment does
not touch the dict). `g`'s own constants and callees join `f`'s guard list (transitively).
Defaults, keywords and closures do not matter (all arguments are passed; top-level defs have no
closure). Units with guarded globals keep the GIL, so no other thread can rebind a name mid-call.
Builtins (`len`, `range`, ...) keep the existing static rule (not rebound in the module); a
run-time `builtins.len = ...` is not guarded today, as before.

**Recursion depth.** CPython raises `RecursionError` when a frame is pushed with
`tstate->py_recursion_remaining <= 0`; the C entry never pushed a frame, so even obs2's single
natives could succeed where CPython fails at the limit. Every entry now requires
`py_recursion_remaining >= K` (K = number of user functions in the unit, an upper bound on frames
along one non-recursive path) or runs the original. A recursive unit's `AIL_MAX_RECURSION_DEPTH`
(today a `#define 50000`) becomes a thread-local set per call to `min(50000, remaining - (K-1))`,
and its "maximum recursion depth exceeded" stop becomes a trap: CPython then re-runs and raises
(or succeeds, if the bound was only conservative). The 50000 cap keeps the C stack bounded when a
program raises `sys.setrecursionlimit`.

**obs4 task 2 (done; constants + calls).** As designed above, plus: a bool module constant is not
added (`to_c` refuses one for the whole slice, which would have cost every other function), and a
local the exact-kind pass proves is a `str` now counts as a str-method receiver (`for ch in src:
ch.isdigit()`). Measured (`obs4_task2.json`, instructions vs CPython, `hand`; `bare+obs` equal to
0.002): natives 47 -> 57, corpus 0.697 -> 0.638 (1.57x vs CPython); `tokenizer` 0.715 -> 0.066
(`count_idents`, `longest_ident`, `digit_count`, `token_weight` now native), `csv_parse` 0.933 ->
0.548 (`COMMA`), `field_valid` 0.387 -> 0.319 (`valid_len`, `score_ok`), `json_parse` 0.882 ->
0.845 (`digits_in`); other modules within noise; all 30 builds byte-identical to the oracle and
live CPython. `test_ail_hybrid_calls.py` covers rebinding, deleting and retyping constants,
reading one before it is assigned, rebinding a callee or its `__code__`, rebinding a recursive
function's own name, and both sides of the recursion limit (with a native at the bottom of a
Python recursion too).

### 5.3 Methods (step a: read-only)

Instances stay CPython objects; nothing about their layout changes. A method goes native by being
**desugared into a synthetic top-level function** that the existing machinery compiles:
`Tree._depth(self, idx, d)` becomes `__ail_m_Tree___depth(__ail_f_left, __ail_f_right, idx, d)`,
each `self.<field>` read becomes a parameter, and each `self.<m>(args)` becomes a call of `m`'s
synthetic function with `m`'s fields passed through (the field set is closed over the class's
self-call graph). The synthetic defs exist only in the analysis source and the selection tree; the
program that runs is the original text plus one install line after the class.

Selection (simplest safe subset): a top-level class with no decorators, no keywords (so no
metaclass), no bases (or only `object`), and only plain `def`s and a docstring in its body; a
method with no decorators whose `self` is used only as `self.<field>` loads (no stores, no bare
`self`) and `self.<method>(...)` calls to other selected methods of the class; every field read
has a kind in int/float/bool/str/list[int]/list[float]. Field kinds are a hypothesis from the
class's own stores (`self.f = e`, `self.f += e`, `self.f.append(e)`, `self.f[i] = e`, solved to a
fixed point with `_Kinds`); a wrong guess only costs fallbacks because the entry checks every
value.

Entry guards, in order, before any native work (all are reads; failure = run the original):

1. `Py_TYPE(self) == C`, C recorded at install. A subclass instance, overriding or not, runs the
   original; so does `C.m(other, ...)`.
2. Class shape: `Py_TYPE(C) == &PyType_Type` (no metaclass), heap type,
   `tp_getattro == PyObject_GenericGetAttr` (no `__getattr__`/`__getattribute__`). For each field,
   `_PyType_Lookup(C, field) == NULL`: no class attribute of that name anywhere in the MRO, so no
   property, slot descriptor or class default can intercept the read, and the generic getattr
   reads only the instance dict (no Python code runs). For each method the body calls on `self`
   (recursion included), `_PyType_Lookup(C, name)` is the installed function object and its
   `__code__` is a recorded code. `_PyType_Lookup` goes through CPython's own type-version method
   cache, so it is correct after any class or base-class change and costs a few ns per name; no
   separate `tp_version_tag` bookkeeping is needed.
3. Instance: each field read once with `PyObject_GetAttr` (missing -> AttributeError cleared ->
   original) and checked exactly like a parameter (lists copied, as today). For each self-called
   method, the instance must not shadow it: `PyObject_GetAttr(self, name)` must be a bound method
   of the installed function on `self` (one allocation per entry, only for methods that call
   methods).

During the native run the GIL is held (fields are containers; owner decision D4), no Python code
runs, and the body stores nothing, so every `self.x` and `self.m` the CPython body would evaluate
resolves to the value read at entry. A trap (index, overflow, recursion depth) re-runs the original
method from the start, which is safe because the body has no side effects.

Monkeypatching: `C.m = other` changes the type (method cache), `obj.m = other` is caught by guard
3, `C.m.__code__ = ...` by the code compare, `obj.__class__ = D` by guard 1, adding a property or
class attribute named like a field by guard 2. Install: `_ail_install_method(name, C, attr)` takes
`C.__dict__[attr]`, checks it is the plain def (code name, positional arity, no varargs) and sets
its vectorcall, as `_ail_install` does for functions. Not covered (they stay in CPython):
`__slots__` fields (slot descriptors fail guard 2 anyway), inherited methods, properties,
classmethods and staticmethods, any field store (step b: write scalar fields back at the end of a
successful call, then `json_parse`), container fields of other kinds.

**Guard cost per entry**: a type compare, ~3 cached type lookups, one `GetAttr` per field, one
bound-method allocation if `self` methods are called, and the list copies. For `tree_build` one
entry per traversal runs 121k recursive native calls, so the guards are noise; `min_key`/`max_key`
copy two 60k-element lists to walk ~20 nodes, slower than CPython for those two (0.0% of the
module; option-3 element-use guards would remove the copy).
