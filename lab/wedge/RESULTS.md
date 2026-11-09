# wedge1: what share of a Rust-rewrite hot path AIL compiles today

Measurement only; the compiler is not changed.  Branch `job-wedge1-11080724`, run 2026-11-07 on a 4-core GitHub Actions runner, CPython 3.12.3, gcc 13.3.0, PyO3 0.22.6 for the Rust bar.  The PyPy column (section 2) was added on 2026-11-08 by `job-pypy1-11090337` with PyPy 7.3.23.

## The answer, in one paragraph

Across 15 small hot-path modules of the kind real projects moved to Rust through PyO3, **29 of 97 top-level functions (29.9%) go native in the CPython hybrid**.  Because the hybrid only accelerates a *top-level function*, and because the hot function of a real module is very often a method, a nested helper or a list-returning builder, the functions that do go native carry only **5.0%** of the corpus's CPython self-time, and the hybrid runs at **0.983x** CPython wall time overall (geomean of hybrid/CPython, median of 5; below 1.0 is faster).  The largest single unlock is **not-a-top-level-function** (19.3% of the kept time): the hybrid's unit is a top-level function, so class methods and nested defs are refused before any type is looked at.  The largest unlock *inside* a function is **list-return-kind** (15.8%): `pymix` cannot track a `tuple`, `bytes` or a list return kind, so the whole function is dropped.  See the ranked table in section 4.

**Against PyPy** (PyPy 7.3.23, section 2): PyPy runs the corpus at **0.159x** CPython time; the AIL standalone binary is **faster than PyPy on 8 of 13 modules** (geomean **0.829x** PyPy) and the hybrid on **0 of 15** (geomean **6.197x**), with PyPy's output byte-identical to CPython on 15 of 15 modules.  The standalone pair is 13 of 15 because the two modules whose default binary stops loudly on int64 need `--exact-int`, so they have no default-run time in `measure.json`.

## 1. The corpus

Fifteen small modules under `lab/wedge/corpus/<kind>/`, each a `<kind>.py` of plain typed Python and a `run.py` driver on a fixed input sized for 1-5 s under CPython.  Each directory also has an `expected.txt`, the CPython oracle: `python3 run.py > expected.txt`, committed so the byte-identical check is reproducible without re-running CPython.  No third-party code.

| module | what it stands for | functions |
| --- | --- | ---: |
| `ast_lint` | lint-like AST walk over nested tuples | 7 |
| `bitset_bloom` | bloom-filter probing and bitset set algebra | 7 |
| `csv_parse` | a CSV-like row/field parser | 6 |
| `dataframe_group` | groupby / sum / filter over parallel row columns | 7 |
| `edit_dist` | edit distance and fuzzy match | 6 |
| `field_valid` | pydantic-like string normalising and field checks | 7 |
| `float_loops` | numeric loops over lists of floats | 8 |
| `graph_search` | BFS and DFS over an adjacency list | 6 |
| `hashing` | FNV / Adler / CRC / djb2 checksums | 7 |
| `json_parse` | a recursive-descent JSON-subset parser | 4 |
| `matrix` | dense n x n integer matrix product | 8 |
| `rolling_stats` | windowed sums, runs and streaks over int samples | 8 |
| `sort_rank` | term counting, insertion ranking, top-k | 7 |
| `tokenizer` | tokenising / lexing a source file | 7 |
| `tree_build` | binary-tree build and traversal | 2 |
| **total** | | **97** |

## 2. Per-module results

`native` is the functions the hybrid build actually wrapped (from `build.json`).  `match` is byte-identical stdout, exit status and last stderr line against `python3 run.py`.  `oracle` is the committed `expected.txt` matching the live CPython run byte for byte.  `pypy match` is the same `expected.txt` against every one of PyPy's five runs (a difference is a PyPy result, recorded in `measure.json` as `pypy_diff`, not fixed in the sources).  Wall time is the median of 5 runs.  `standalone` is the binary from `ail compile run.py --syntax python`; `(+exact)` means the default build stopped loudly on int64 overflow and `--exact-int` then built a matching binary.

| module | funcs | native | native share | oracle | hybrid match | pypy match | standalone | CPython s | PyPy s | hybrid s | hybrid / CPython | hybrid / PyPy | standalone / PyPy |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `ast_lint` | 7 | 0 | 0% | yes | yes | yes | match | 1.739 | 0.313 | 1.842 | 1.060x | 5.890x | 2.2558x |
| `bitset_bloom` | 7 | 2 | 29% | yes | yes | yes | match (+exact) | 1.809 | 0.209 | 1.806 | 0.999x | 8.628x | n/a |
| `csv_parse` | 6 | 1 | 17% | yes | yes | yes | match | 2.04 | 0.362 | 1.884 | 0.923x | 5.206x | 0.3875x |
| `dataframe_group` | 7 | 3 | 43% | yes | yes | yes | match | 0.972 | 0.363 | 0.899 | 0.924x | 2.475x | 0.0634x |
| `edit_dist` | 6 | 3 | 50% | yes | yes | yes | match | 2.232 | 0.25 | 2.232 | 1.000x | 8.922x | 7.7756x |
| `field_valid` | 7 | 4 | 57% | yes | yes | yes | match | 2.11 | 0.416 | 2.183 | 1.035x | 5.252x | 0.2646x |
| `float_loops` | 8 | 0 | 0% | yes | yes | yes | match | 2.198 | 0.584 | 2.206 | 1.003x | 3.774x | 0.2610x |
| `graph_search` | 6 | 0 | 0% | yes | yes | yes | match | 2.076 | 0.537 | 2.023 | 0.974x | 3.769x | 3.6574x |
| `hashing` | 7 | 0 | 0% | yes | yes | yes | match (+exact) | 1.665 | 0.174 | 1.666 | 1.001x | 9.559x | n/a |
| `json_parse` | 4 | 3 | 75% | yes | yes | yes | match | 1.415 | 0.247 | 1.275 | 0.901x | 5.153x | 5.7537x |
| `matrix` | 8 | 5 | 62% | yes | yes | yes | match | 2.894 | 0.081 | 2.905 | 1.004x | 35.702x | 0.2870x |
| `rolling_stats` | 8 | 4 | 50% | yes | yes | yes | match | 2.664 | 0.368 | 2.424 | 0.910x | 6.582x | 0.3263x |
| `sort_rank` | 7 | 3 | 43% | yes | yes | yes | match | 1.504 | 0.334 | 1.531 | 1.018x | 4.578x | 4.8123x |
| `tokenizer` | 7 | 1 | 14% | yes | yes | yes | match | 0.885 | 0.102 | 0.883 | 0.998x | 8.669x | 0.9153x |
| `tree_build` | 2 | 0 | 0% | yes | yes | yes | match | 1.97 | 0.522 | 1.987 | 1.009x | 3.805x | 0.3391x |

**Silent differences: zero.**  Every hybrid build matched CPython on every module; the standalone build matched on 13 of 15 by default and all 15 with `--exact-int`.  The two default-build stops are loud (`OverflowError: integer overflow in * ... --exact-int gives exact ints`), never a wrong answer.

**PyPy output: 15 of 15 modules byte-identical.**  PyPy ran the same `run.py` on the same input, five times, and every run was compared with the committed `expected.txt`.

### What the wall-time columns say

The hybrid runs at **0.983x** CPython (`hybrid / CPython` below 1.0 means faster; geomean over 15 modules, range 0.901x-1.06x -- the same convention as the table column).  It is not faster in the aggregate because the functions that went native carry only 5.0% of the self time; the rest is still interpreted.  The standalone binary is much faster where the whole program types (matrix 2.89 s vs 0.023 s, dataframe_group 0.97 s vs 0.023 s, rolling_stats 2.66 s vs 0.12 s, field_valid 2.11 s vs 0.11 s), so the boundary is not the C quality -- it is the *selection*.

### What PyPy does to the same fifteen modules

PyPy needs no build and no types: it runs `run.py` and JIT-compiles the hot loops.  On this corpus it is **0.159x** CPython wall time (geomean over 15 modules that matched the oracle), so a plain CPython program already gets most of what this benchmark is about.  The hybrid, which keeps the function boundary, lands at **6.197x** PyPy (0 of 15 modules faster than PyPy) and the standalone binary at **0.829x** PyPy (8 of 13 faster).  Ratios below 1.0 mean AIL is faster; `measure.json` holds every median.

Where the two AIL arms lose to PyPy is the module whose hot function is a plain method or a container-returning builder: the hybrid leaves it on CPython (so it pays CPython plus the boundary) and PyPy makes it fast.  Where the standalone binary types the whole driver it beats PyPy by the C-quality margin the table shows.

The standalone arm is not uniformly ahead: it loses to PyPy on **5 of 13** measured modules, worst on `ast_lint` 2.26x, `graph_search` 3.66x, `sort_rank` 4.81x, `json_parse` 5.75x.  Those are the programs whose data model (tuple-heavy ASTs, string-keyed dicts, per-element object churn) costs more in the typed lowering than a JIT that specializes the same shapes at run time, so the comparison is not "C beats a JIT" on this corpus -- it is task-dependent.

## 3. The Rust bar

`lab/wedge/rust/` is a hand-written PyO3 0.22 extension (`hotrust`) holding the single hottest function of five modules, written the way a PyO3 user writes it.  `rust_bar.py` measures two columns:

* **call**: the hot function alone, corpus module vs Rust, median of 5 in one process;
* **whole**: the module's own `run.py`, once with the one function rebound to the Rust version, median of 5.

| module | function | call: CPython ms | call: Rust ms | call ratio | whole: CPython s | whole: Rust s | whole ratio | outputs agree |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `edit_dist` | `levenshtein` | 0.084 | 0.001 | 62.3x | 2.202 | 0.121 | 18.19x | yes |
| `float_loops` | `dot` | 248.355 | 124.232 | 2x | 2.209 | 2.055 | 1.07x | yes |
| `matrix` | `mat_mul` | 2761.086 | 13.523 | 204.2x | 2.888 | 0.063 | 45.8x | yes |
| `rolling_stats` | `window_sums` | 388.205 | 139.356 | 2.8x | 2.648 | 1.854 | 1.43x | yes |
| `tokenizer` | `count_idents` | 237.543 | 3.103 | 76.6x | 0.866 | 0.636 | 1.36x | yes |

Rewriting one function in Rust is worth **2x-204x** on that function, but only **1.07x-45.8x** on the program, because the rest of the program is still Python.  AIL's hybrid on the same five modules takes **0.91x-1.004x** of CPython time in the table's `hybrid / CPython` convention: it is at best 1.1x faster (`rolling_stats`), and parity or slower on the rest.  That is the size of the gap the boundary opens: the Rust rewrite wins **1.07x-45.8x** whole-program, AIL wins at most **1.1x**.

## 4. Refusal reasons, ranked by the hot-path time each keeps on CPython

Method: cProfile on each `run.py` gives the self-time (`tottime`) of every function.  Each function that the hybrid did **not** wrap is charged its self-time to the one gate that stopped it.  The gates are the real ones, in order: `pymix.analyze` (is it a candidate at all), `pyfunc.to_c` + `pyboxed2._mix_validate_signature` (does the emitter accept it and does its prototype match the ABI the hybrid builds), then `ail_cpython_hybrid._select` (the no-trap body rule, parameter and result kinds, list mutation).  `lab/wedge/boundary.py` reports which gate stopped each function and with what message.

`share` is the percentage of the corpus's **profiled** whole-function self time (44.2 s across 15 modules).  `native` time is 2.19 s = 5.0% of it.  The profiled base is 1.57x the 28.17 s of CPython wall time in section 2, because cProfile adds per-call overhead; the shares rank the refused functions but are **not shares of real wall time** (for example `ast_lint` is 5.67 s of self time for a 1.739 s program, `tree_build` 5.80 s for 1.97 s).

A first gate is only a **ceiling**: `_select` applies `_unsafe_body` and then `_list_param_mutated`, so a function fixed at its first gate can still be refused for a subscript, a call, an index store, a division or passing a list parameter on to a call (including `len`).  Of the 11 list-return functions 0 pass that body rule, of the 7 tuple-parameter 0, of the 6 nested-list 1, of the 7 list-float 2.  The `solo` column is the time of the functions with no other body gate; the `W4` column adds the index/index-store fix (W4) but not the list-parameter gate.

| # | reason | self time s | share | solo self s | solo funcs | +W4 self s | +W4 funcs | functions | modules | example functions |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | not-a-top-level-function | 8.53 | 19.3% | 0 | 0 | 0 | 0 | 23 | 3 | `Frame`, `__init__`, `rows` |
| 2 | list-return-kind | 6.98 | 15.8% | 0 | 0 | 3.08 | 3 | 11 | 6 | `bloom_set`, `make_hashes`, `group_count` |
| 3 | tuple-parameter | 5.67 | 12.8% | 0 | 0 | 0 | 0 | 7 | 1 | `count_ints`, `count_tag`, `has_tag` |
| 4 | indexing-can-raise | 5.58 | 12.6% | 0 | 1 | 0 | 1 | 10 | 6 | `bloom_probe`, `set_intersect`, `weighted_sum` |
| 5 | nested-list-annotation | 3.91 | 8.9% | 0.01 | 1 | 0.01 | 1 | 6 | 1 | `bfs_reach`, `build_graph`, `degree_sum` |
| 6 | list-str-parameter | 2.48 | 5.6% | 0 | 0 | 0 | 0 | 3 | 2 | `split_lines`, `count_terms`, `hash_spread` |
| 7 | call-can-raise | 2.21 | 5.0% | 1.32 | 4 | 2.21 | 6 | 6 | 3 | `djb2`, `digits_in`, `count_idents` |
| 8 | untyped-return-kind | 2.01 | 4.6% | 2.01 | 5 | 2.01 | 5 | 5 | 2 | `is_simple_email`, `score_ok`, `valid_len` |
| 9 | module-constant | 1.63 | 3.7% | 0.93 | 3 | 0.93 | 3 | 4 | 1 | `count_fields`, `field_chars`, `max_field_len` |
| 10 | bytes-parameter | 1.48 | 3.4% | 1.48 | 6 | 1.48 | 6 | 6 | 1 | `adler32_simple`, `crc32_table_free`, `fnv1a` |
| 11 | list-float-abi | 1.26 | 2.8% | 0.21 | 2 | 0.21 | 2 | 7 | 1 | `blend`, `dot`, `max_abs` |
| 12 | division-can-raise | 0.24 | 0.5% | 0.13 | 2 | 0.13 | 2 | 3 | 3 | `multiples`, `scaled_total`, `mean_scaled` |
| 13 | user-class-annotation | 0.01 | 0.0% | 0 | 1 | 0 | 1 | 2 | 1 | `build_tree`, `count_nodes` |
| 14 | unannotated-list-parameter | 0.01 | 0.0% | 0 | 0 | 0 | 0 | 2 | 1 | `best_match`, `total_length` |
| 15 | list-return | 0 | 0.0% | 0 | 0 | 0 | 0 | 1 | 1 | `top_score` |

Read the `solo` column, not the ceiling.  By solo-achievable time the five largest fixes are untyped-return-kind (2.01 s), bytes-parameter (1.48 s), call-can-raise (1.32 s), module-constant (0.93 s), list-float-abi (0.21 s).  The five first-gate reasons below are still the biggest when their prerequisites are fixed, but **W4 (indexing-can-raise) is the prerequisite for W2/W3/W6**, and the call, division and list-parameter rules are additional gates; so the W1-W6 order is dependency-aware, not the ceiling order.

### The five reasons that matter, spelled out

1. **not-a-top-level-function** -- the hybrid's unit is a top-level `def`, so a class method, a nested helper or a constructor is refused before any typing happens.  This is the largest single bucket because the hottest code in a real module is often a method (`Tree._inorder` 2.15 s of `tree_build`'s 5.8 s of function self time; the three tree methods alone are 5.69 s).  The corpus's 8.53 s is plain methods taking `self`, which the two-hour W1 scope (staticmethods and closures) does not cover, so W1 measures 0 solo here.
2. **list-return-kind** -- `-> list[int]` / `-> list[str]` / `-> list[float]`.  `pymix` has no return kind for a container, and the boundary has no ABI for one.  The first gate alone accelerates **0 of 11**: every body also indexes, calls or divides.  With W4 also applied, 3 of 11 (`group_count`, `identity`, `mat_mul`, 3.08 s) become reachable; the rest still need the call, division or list-parameter rule.
3. **tuple-parameter** -- a `tuple` parameter (`node: tuple`) is not a tracked kind.  `ast_lint`'s recursive walk is 5.7 s of the corpus, but all 7 functions also index and call, so W3 alone accelerates **0 of 7**; W4 and the call rule are additional prerequisites for the whole 5.67 s.
4. **indexing-can-raise** -- `_unsafe_body` refuses any subscript, because the typed clone cannot reproduce `IndexError` back into the caller's `try`.  It is the most common second gate, but only 1 of the 10 indexing functions (`trace`) has no other body gate, because 8 also call and 1 divides; `levenshtein` appends to a list as well, so it needs the call rule too.  W4 alone moves 1 function; its value is as the prerequisite for W2/W6.
5. **nested-list-annotation** -- `list[list[int]]` (an adjacency list) is not a tracked parameter kind.  Only 1 of 6 (`edges_above`, 0.01 s) has no other body gate; the other 5 call, so W5 alone accelerates 1 and the 3.9 s is a ceiling.

The rest, in order: `list-str-parameter` (`list[str]`, 2.5 s), `call-can-raise` (`_unsafe_body` refuses a call to a user function or a `str` method it cannot prove pure, 2.2 s), `untyped-return-kind` (`return a and b` -- a `BoolOp` return has no resolved kind, 2.0 s), `module-constant` (a module-level `COMMA = ","` is "read before it is assigned", 1.6 s), `bytes-parameter` (`bytes` is not a tracked parameter kind, 1.5 s), `list-float-abi` (see below, 1.3 s), `division-can-raise` (0.2 s), `user-class-annotation` and `unannotated-list-parameter` (0.01 s each), `list-return` (0.0 s).

### A defect found on the way: `list[float]` cannot be wrapped at all

`float_loops` gets none of its 8 functions, but `list[float]` ABI is **not** the only reason: the typed emitter accepts 7 of the 8, and `scale_into` is refused earlier by `pymix` as `unresolved-return` (family list-return-kind), so it never reaches the ABI gate.  For the 7 that do, `pyfunc.to_c` spells a `list[float]` parameter as a whole `ail_flist` value (`double dot(ail_flist v_a, ail_flist v_b)`); `pyboxed2._mix_validate_signature` demands the `const double *v_a, int64_t v_a_len` pair it demands for `list[int]`, and `ail_cpython_hybrid._c_proto` / `_wrapper_source` build the same pointer+length call.  Every `list[float]` candidate therefore fails the ABI cross-check and stays boxed.  This is not a semantic limit: the whole-program typed build compiles the same module on the typed path (2.20 s -> 0.15 s), and the hybrid wrapper already allocates and fills the `double *` buffer -- it just hands it over in the wrong shape (`ail_flist` is `{double *p; int64_t n, cap}`, so a value can be built in one line).  With the ABI spelling fixed only `max_abs` and `sq_sum` have no other body gate (2 of the 7); `dot`/`blend` also index and pass a list parameter to `len()` (W4 plus the list-parameter gate), `mean`/`variance`/`norm` divide by a non-constant, and `scale_into` needs W2.  With W4 too, 2 of the 7 become reachable (0.21 s); the module does not go from 0 to 8.

### A second defect: 54 of the 68 refusals are silent

`docs/STRATEGY.md` promises that "when a function stays on CPython, the build says which line keeps it there and how to fix it".  It does not.  `build.json` carries a `rejected` map with a reason only for a function that reached a *unit* and was then dropped by `_select`; a function pymix or the emitter refused never gets a unit, so nothing is recorded and the key is simply absent.  Across this corpus **54 of the 68 functions that stayed on CPython (79.4%) carry no reason at all**, including every function in `ast_lint`, `float_loops`, `graph_search`, `tokenizer`'s `is_ident_*`, and `csv_parse`'s module constant group.  The rest of `STRATEGY.md`'s loop -- an AI reads the reason, applies the fix -- cannot close on 54 of the 68 refusals.

The information exists: `lab/wedge/boundary.py` recovers it by re-running `pymix.analyze` and `to_c` itself, which is exactly what `_analysis` already does inside a subprocess.  Surfacing it is a reporting change in `ail_cpython_hybrid._select`, not a compiler change; W0 below covers it.

## 5. Ready-to-queue tasks, each 2 hours or less

Ordered W0 (reporting, no time), then W4 (the body prerequisite), then W2/W3/W6 that depend on it, then W5 and W1.  Each names the reason, the test that guards it, and the measured ceiling plus the solo gain.  By solo-achievable time the ranking is different (section 4); this set is the five largest first-gate ceilings plus the prerequisite, not the achievable order.

### W0 -- silent-refusal (unlocks the other tasks; moves no time itself)

Surface the refusal reason in `build.json` for a function that never reaches a unit.  Today `_select` records a reason only for a function it saw and dropped; a function that `pymix.analyze` or `to_c` refuses gets no unit, so `rejected` has no key and the build is silent (54 of 68 refusals here).  `lab/wedge/boundary.py` already recovers the reason by re-running `pymix.analyze` and `to_c`; move that call into the same place `_analysis` runs, and write `{function: {gate, reason}}` under `rejected` even when `_select` never produced a unit.  This is a reporting change, not a compiler change: no function goes native.  Its gain is that the other tasks below become queueable -- without it 54 of 68 refusals cannot be acted on.

**Guard:** `build.json` for `ast_lint`, `float_loops`, `graph_search` and `tokenizer` lists a `gate` and `reason` for every function that stayed on CPython.  Guard: a new `test_ail_cpython_hybrid` case whose module has one pymix-refused and one emitter-refused function, asserting both appear in `rejected`; plus `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

**Gain:** measured: makes 54 of 68 refusals (79.4%) name their gate and fix; 0 s moves native by itself.

### W4 -- indexing-can-raise (measured ceiling 12.6% of the corpus self time)

Let a clone that may raise `IndexError` fall back instead of being refused.  `_unsafe_body` refuses every `Subscript` outright, load or store.  The emitted typed clone already has a trap path: make the index check set the per-function mix flag (the same `extern int <mangled>__mix_overflow` the int64 path uses), return a zero, and let the Python wrapper re-run the original function when the flag is set.  The wrapper already catches `Fallback`, so the caller's `try/except IndexError` still sees CPython's exception; a call that never indexes out of range pays one flag test.  This is the prerequisite for W2/W3/W6, not a large solo unlock.

**Guard:** `matrix.trace` (list[int] parameter, int return, `m[i*n+i]`) is the one indexing function whose body has no other gate; it is accelerated and its driver stays byte-identical.  `edit_dist.levenshtein` (3.6 s) also appends to a list, so it needs the call rule as well, not W4 alone.  Guard: a new `test_ail_cpython_hybrid` case with an in-range index, an index exactly at `len`, a negative index and an empty list; plus the four required modules.

**Gain:** measured: solo 0 s (1 of 10 functions, `trace`); W4 also unblocks 3.08 s of list-return (3 functions) and 0.21 s of list-float (2 functions).  The 5.6 s first-gate ceiling is reached only when the call and division rules are applied too.

### W2 -- list-return-kind (measured ceiling 15.8% of the corpus self time)

Give `pymix` and the boundary a `list[int]` / `list[float]` return kind.  `pymix` reports `unresolved-return` for a body whose `return xs` is a list, and the hybrid `_wrapper_source` has no C path for a returned list.  Add `pymix.LIST_INT` /`LIST_FLOAT` to the return kinds it resolves from a `return <list literal or list name>` and a list-append loop, and add a wrapper branch that returns `PyList_New` filled from the emitted `(const int64_t *out, int64_t n)` out-parameter pair the library ABI already uses (`compile-library`).

**Guard:** W2 alone accelerates **0 of 11** functions because every body also indexes or calls.  With W4 also applied (covering subscript stores), `group_count`, `identity`, `mat_mul` (3.08 s) become native and their drivers stay byte-identical; `group_sum` also passes a list parameter to `len()` (the `_list_param_mutated` gate), `window_sums`, `make_hashes`, `row_sums`, `make_samples`, `scale_into` and `top_indices` still need the call rule, and `bloom_set` also divides.  Guard: a new `test_ail_cpython_hybrid` case with an empty list return, a one-element list return and a 100k-element list return; plus `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

**Gain:** measured: solo 0.0 s; W2+W4 3.08 s of 44.2 s (3 of 11 functions); the 7.0 s first-gate ceiling is not reachable by this task alone.

### W3 -- tuple-parameter (measured ceiling 12.8% of the corpus self time)

Track a `tuple` parameter as an opaque homogeneous element stream.  `ast_lint` passes nested tuples of str/int; a real project's AST walk passes a node object.  Two hours buys the narrow case: a parameter annotated `tuple` whose body only calls `isinstance(child, tuple)`, `len(node)` and `node[i]` for a `range()` index.  Lower it to the existing `ail_list` of boxed values the general path already has, or refuse it by name with a fix (`write instead: node: list[object]`) so the AI can act.

**Guard:** W3 alone accelerates **0 of 7**: each function both indexes and calls.  With W4 and the call rule, all 7 (`node_count`, `leaves`, `max_depth`, `sum_ints`, ...) can become native and the driver's 7 printed lines stay byte-identical.  Guard: a new case with an empty tuple, a one-element tuple, a nested tuple 8 deep, and an index from a list item and from a dict value; plus the four required modules.

**Gain:** measured: solo 0.0 s; needs W4+call; the 5.7 s first-gate time is the ceiling, not this task's gain.

### W6 -- list-float-abi (measured ceiling 2.8% of the corpus self time)

Fix the `ail_flist` prototype mismatch (section 4).  Either teach `_mix_validate_signature` that `ail_flist v_x` is the same ABI as `const double *v_x, int64_t v_x_len` (the call site already builds that pair), or make `to_c` spell a mixed-mode `list[float]` parameter the pointer+len way.  This is the cheapest task in the list: one prototype spelling.

**Guard:** With W6 alone `max_abs` and `sq_sum` become native (2 of 7, 0.21 s); W4 adds nothing, because `dot` and `blend` also index and pass a list parameter to `len()` (W4 plus the `_list_param_mutated` gate), `mean`/`variance` divide by a non-constant, `variance` also calls, `norm` uses `**`, and `scale_into` is list-return-kind (W2).  So `float_loops` does **not** go from 0 to 8.  Its driver stays byte-identical on all 9 printed lines.  Guard: a new `test_ail_cpython_hybrid` case with an empty `list[float]`, a NaN, `-0.0`, and a value that arrives through an argument, a list item and a dict value; plus the four required modules.

**Gain:** measured: solo 0.21 s (2 of 7); W6+W4 also 0.21 s (2 of 7); only the division, call and list-parameter gates plus W2 for `scale_into` reach the 1.26 s ceiling.

### W5 -- nested-list-annotation (measured ceiling 8.9% of the corpus self time)

Track `list[list[int]]`.  `pymix` has no kind for it, so every `graph_search` function is refused at the candidate stage.  The typed path already lowers `list[list[int]]` inside a whole-program build (the nested-lists test module exists); the gap is the *boundary* ABI and `pymix`'s kind fixed point.  Two hours: add `pymix.LIST_LIST_INT`, resolve it from the annotation, and map it to the existing `ail_list`-of-`ail_list` the typed emitter's nested-list path builds, with the wrapper copying each inner list as one buffer.

**Guard:** Only `edges_above` (0.01 s) has no other body gate, so W5 alone accelerates 1 of 6; W4 does not change that, because the other 5 call.  `bfs_reach`, `dfs_count`, `degree_sum` and `max_degree` need the call rule too.  Guard: a new case with an empty outer list, an outer list with one empty inner list, a ragged inner list, and an inner list reached through an argument and through a dict value; plus the four required modules.

**Gain:** measured: solo 0.01 s (1 of 6); the 3.9 s first-gate time is the ceiling.

### W1 -- not-a-top-level-function (measured ceiling 19.3% of the corpus self time)

Accelerate a method and a nested def, not only a top-level `def`.  Today `ail_cpython_hybrid._select` looks functions up in `_top_level_functions(tree)` and the unit is one module-level `def`; a `Class.method` or a closure is skipped before any typing.  Extend the unit to `ClassName.method` by mangling the C symbol with the class name, wrapping it with a `METH_VARARGS` entry, and rebinding it on the class (`C.m = _ail_hybrid_make(_native.m, C.m)`) once the class exists.  Self is not an ABI kind, so only an `@staticmethod` (and a nested def that closes over nothing) is in scope for two hours; a plain method takes `self` and needs a container ABI, which is a later task.

**Guard:** A module with an `@staticmethod` hot helper is listed as accelerated and its output is byte-identical.  The corpus's `Tree._inorder` / `_depth` / `_height` are plain methods taking `self`, so they are **not** expected to move under this scope; the 19.3% is the ceiling for the full method ABI, not this task.  Guard: `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

**Gain:** measured: solo 0 s on this corpus (the 8.5 s is plain methods); the reachable part (staticmethods and closures) is not present here, so treat 19.3% as the ceiling.

## 6. Reproduce

```sh
for d in lab/wedge/corpus/*/; do (cd "$d" && python3 -B run.py > expected.txt); done  # oracles
python3 lab/wedge/census.py -j 2      # builds, native counts, byte-identical + oracle check
python3 lab/wedge/boundary.py          # which gate refused each function, and why
python3 lab/wedge/measure.py -j 2      # wall time, median of 5, plus cProfile
python3 lab/wedge/rust_bar.py          # cargo build + the PyO3 bar
python3 lab/wedge/analyse.py           # ranks the reasons by hot-path time
python3 lab/wedge/report.py            # renders this file
```

`census.py` and `measure.py` take `-j 2`; on a 4-core runner the whole pipeline is about 35 minutes, dominated by the 97 hybrid analyses at ~10 s each.

## 7. What is not measured

* Instruction counts: `perf_event_open` is denied on this runner, and callgrind was not used because the job is a wall-time question.
* The Rust bar covers 5 of 15 modules, as the task allows; the rest have no hand-written PyO3 twin.  `rust_bar.json` stores a length and SHA-256 digest of each function's return value, not the value itself (`rolling_stats` returns a 21 MB list); the `outputs agree` column is the live in-process `MATCH` comparison.
* The hybrid analysis runs under `--exact-int`, so a module whose values exceed int64 can still be analysed; the *standalone* column needs `--exact-int` explicitly and is marked `(+exact)` when it does.
* The two `--exact-int` rows are real: `bitset_bloom` and `hashing` multiply past 2**63 in the driver, so the default 64-bit build stops loudly.  That is the documented int64 stop, not a silent difference.
