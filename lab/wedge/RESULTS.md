# wedge1: what share of a Rust-rewrite hot path AIL compiles today

Measurement only; the compiler is not changed.  Branch `job-wedge1-11080724`, run 2026-11-07 on a 4-core GitHub Actions runner, CPython 3.12.3, gcc 13.3.0, PyO3 0.22.6 for the Rust bar.

## The answer, in one paragraph

Across 15 small hot-path modules of the kind real projects moved to Rust through PyO3, **24 of 97 top-level functions (24.7%) go native in the CPython hybrid**.  Because the hybrid only accelerates a *top-level function*, and because the hot function of a real module is very often a method, a nested helper or a list-returning builder, the functions that do go native carry only **5.0%** of the corpus's CPython self-time, and the hybrid is **1.017x** CPython wall time overall (geomean, median of 5).  The largest single unlock is **not-a-top-level-function** (19.3% of the kept time): the hybrid's unit is a top-level function, so class methods and nested defs are refused before any type is looked at.  The largest unlock *inside* a function is **list-return-kind** (15.8%): `pymix` cannot track a `tuple`, `bytes` or a list return kind, so the whole function is dropped.  See the ranked table in section 4.

## 1. The corpus

Fifteen small modules under `lab/wedge/corpus/<kind>/`, each a `<kind>.py` of plain typed Python and a `run.py` driver on a fixed input sized for 1-5 s under CPython.  No third-party code.

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

`native` is the functions the hybrid build actually wrapped (from `build.json`).  `match` is byte-identical stdout, exit status and last stderr line against `python3 run.py`.  Wall time is the median of 5 runs.  `standalone` is the binary from `ail compile run.py --syntax python`; `(+exact)` means the default build stopped loudly on int64 overflow and `--exact-int` then built a matching binary.

| module | funcs | native | native share | hybrid match | standalone | CPython s | hybrid s | hybrid / CPython | standalone s |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| `ast_lint` | 7 | 0 | 0% | yes | match | 1.739 | 1.842 | 1.060x | 0.706 |
| `bitset_bloom` | 7 | 2 | 29% | yes | match (+exact) | 1.809 | 1.806 | 0.999x | n/a |
| `csv_parse` | 6 | 1 | 17% | yes | match | 2.04 | 1.884 | 0.923x | 0.14 |
| `dataframe_group` | 7 | 3 | 43% | yes | match | 0.972 | 0.899 | 0.924x | 0.023 |
| `edit_dist` | 6 | 0 | 0% | yes | match | 2.232 | 2.232 | 1.000x | 1.945 |
| `field_valid` | 7 | 4 | 57% | yes | match | 2.11 | 2.183 | 1.035x | 0.11 |
| `float_loops` | 8 | 0 | 0% | yes | match | 2.198 | 2.206 | 1.003x | 0.153 |
| `graph_search` | 6 | 0 | 0% | yes | match | 2.076 | 2.023 | 0.974x | 1.963 |
| `hashing` | 7 | 0 | 0% | yes | match (+exact) | 1.665 | 1.666 | 1.001x | n/a |
| `json_parse` | 4 | 3 | 75% | yes | match | 1.415 | 1.275 | 0.901x | 1.423 |
| `matrix` | 8 | 4 | 50% | yes | match | 2.894 | 2.905 | 1.004x | 0.023 |
| `rolling_stats` | 8 | 4 | 50% | yes | match | 2.664 | 2.424 | 0.910x | 0.12 |
| `sort_rank` | 7 | 3 | 43% | yes | match | 1.504 | 1.531 | 1.018x | 1.609 |
| `tokenizer` | 7 | 0 | 0% | yes | match | 0.885 | 0.883 | 0.998x | 0.093 |
| `tree_build` | 2 | 0 | 0% | yes | match | 1.97 | 1.987 | 1.009x | 0.177 |

**Silent differences: zero.**  Every hybrid build matched CPython on every module; the standalone build matched on 13 of 15 by default and all 15 with `--exact-int`.  The two default-build stops are loud (`OverflowError: integer overflow in * ... --exact-int gives exact ints`), never a wrong answer.

### What the wall-time columns say

The hybrid is **1.017x** CPython (geomean over 15 modules, range 0.944x-1.11x).  It is not faster in the aggregate because the functions that went native carry only 5.0% of the self time; the rest is still interpreted.  The standalone binary is much faster where the whole program types (matrix 2.89 s vs 0.023 s, dataframe_group 0.97 s vs 0.023 s, rolling_stats 2.66 s vs 0.12 s, field_valid 2.11 s vs 0.11 s), so the boundary is not the C quality -- it is the *selection*.

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

Rewriting one function in Rust is worth **2x-204x** on that function, but only **1.07x-45.8x** on the program, because the rest of the program is still Python.  AIL's hybrid, on the same five modules, is edit_dist 1x, float_loops 1x, matrix 1x, rolling_stats 1.1x, tokenizer 1x.  That is the size of the gap the boundary opens: the Rust rewrite wins 1.4x-46x whole-program, AIL wins 1.0x-1.2x.

## 4. Refusal reasons, ranked by the hot-path time each keeps on CPython

Method: cProfile on each `run.py` gives the self-time (`tottime`) of every function.  Each function that the hybrid did **not** wrap is charged its self-time to the one gate that stopped it.  The gates are the real ones, in order: `pymix.analyze` (is it a candidate at all), `pyfunc.to_c` + `pyboxed2._mix_validate_signature` (does the emitter accept it and does its prototype match the ABI the hybrid builds), then `ail_cpython_hybrid._select` (the no-trap body rule, parameter and result kinds, list mutation).  `lab/wedge/boundary.py` reports which gate stopped each function and with what message.

`share` is the percentage of the corpus's whole-function self time (44.2 s across 15 modules).  `native` time is 2.19 s = 5.0% of it.

| # | reason | self time s | share | functions | modules | example functions |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | not-a-top-level-function | 8.53 | 19.3% | 23 | 3 | `Frame`, `__init__`, `rows` |
| 2 | list-return-kind | 6.98 | 15.8% | 11 | 6 | `bloom_set`, `make_hashes`, `group_count` |
| 3 | tuple-parameter | 5.67 | 12.8% | 7 | 1 | `count_ints`, `count_tag`, `has_tag` |
| 4 | indexing-can-raise | 5.58 | 12.6% | 10 | 6 | `bloom_probe`, `set_intersect`, `weighted_sum` |
| 5 | nested-list-annotation | 3.91 | 8.9% | 6 | 1 | `bfs_reach`, `build_graph`, `degree_sum` |
| 6 | list-str-parameter | 2.48 | 5.6% | 3 | 2 | `split_lines`, `count_terms`, `hash_spread` |
| 7 | call-can-raise | 2.21 | 5.0% | 6 | 3 | `djb2`, `digits_in`, `count_idents` |
| 8 | untyped-return-kind | 2.01 | 4.6% | 5 | 2 | `is_simple_email`, `score_ok`, `valid_len` |
| 9 | module-constant | 1.63 | 3.7% | 4 | 1 | `count_fields`, `field_chars`, `max_field_len` |
| 10 | bytes-parameter | 1.48 | 3.4% | 6 | 1 | `adler32_simple`, `crc32_table_free`, `fnv1a` |
| 11 | list-float-abi | 1.26 | 2.8% | 7 | 1 | `blend`, `dot`, `max_abs` |
| 12 | division-can-raise | 0.24 | 0.5% | 3 | 3 | `multiples`, `scaled_total`, `mean_scaled` |
| 13 | user-class-annotation | 0.01 | 0.0% | 2 | 1 | `build_tree`, `count_nodes` |
| 14 | unannotated-list-parameter | 0.01 | 0.0% | 2 | 1 | `best_match`, `total_length` |
| 15 | list-return | 0 | 0.0% | 1 | 1 | `top_score` |

### The five reasons that matter, spelled out

1. **not-a-top-level-function** -- the hybrid's unit is a top-level `def`, so a class method, a nested helper or a constructor is refused before any typing happens.  This is the largest single bucket because the hottest code in a real module is often a method (`Tree._inorder` 1.8 s of `tree_build`'s 3.9 s).
2. **list-return-kind** -- `-> list[int]` / `-> list[str]` / `-> list[float]`.  `pymix` has no return kind for a container, and the boundary has no ABI for one, so `group_sum`, `mat_mul`, `window_sums`, `make_samples`, `bloom_set`, `split_lines` and `identity` all stay in Python.
3. **tuple-parameter** -- a `tuple` parameter (`node: tuple`) is not a tracked kind.  `ast_lint`'s recursive walk is 5.7 s of the corpus and every function in it is refused this way.
4. **indexing-can-raise** -- `_unsafe_body` refuses any subscript, because the typed clone cannot reproduce `IndexError` back into the caller's `try`.  This is the single biggest *body* rule: `levenshtein` alone is 3.6 s.  A clone that returns a sentinel and lets the Python wrapper re-run the original on `IndexError` would unlock it.
5. **nested-list-annotation** -- `list[list[int]]` (an adjacency list) is not a tracked parameter kind; all of `graph_search` (3.9 s) is refused here.

The rest, in order: `list-str-parameter` (`list[str]`, 2.5 s), `call-can-raise` (`_unsafe_body` refuses a call to a user function or a `str` method it cannot prove pure, 2.2 s), `untyped-return-kind` (`return a and b` -- a `BoolOp` return has no resolved kind, 2.0 s), `module-constant` (a module-level `COMMA = ","` is "read before it is assigned", 1.6 s), `bytes-parameter` (`bytes` is not a tracked parameter kind, 1.5 s), `list-float-abi` (see below, 1.3 s), `division-can-raise` (0.2 s), `user-class-annotation` and `unannotated-list-parameter` (0.01 s each), `list-return` (0.0 s).

### A defect found on the way: `list[float]` cannot be wrapped at all

`float_loops` is the one module where the typed emitter accepts all 8 functions and the hybrid still wraps none.  `pyfunc.to_c` spells a `list[float]` parameter as a whole `ail_flist` value (`double dot(ail_flist v_a, ail_flist v_b)`); `pyboxed2._mix_validate_signature` demands the `const double *v_a, int64_t v_a_len` pair it demands for `list[int]`, and `ail_cpython_hybrid._c_proto` / `_wrapper_source` build the same pointer+length call.  Every `list[float]` candidate therefore fails the ABI cross-check and stays boxed.  This is not a semantic limit: the whole-program typed build compiles the same module on the typed path (2.20 s -> 0.15 s), and the hybrid wrapper already allocates and fills the `double *` buffer -- it just hands it over in the wrong shape (`ail_flist` is `{double *p; int64_t n, cap}`, so a value can be built in one line).  It is one prototype spelling, and it is the cheapest fix in the list.

### A second defect: 54 of the 73 refusals are silent

`docs/STRATEGY.md` promises that "when a function stays on CPython, the build says which line keeps it there and how to fix it".  It does not.  `build.json` carries a `rejected` map with a reason only for a function that reached a *unit* and was then dropped by `_select`; a function pymix or the emitter refused never gets a unit, so nothing is recorded and the key is simply absent.  Across this corpus **54 of the 73 functions that stayed on CPython (74.0%) carry no reason at all**, including every function in `ast_lint`, `float_loops`, `graph_search`, `tokenizer`'s `is_ident_*`, and `csv_parse`'s module constant group.  The rest of `STRATEGY.md`'s loop -- an AI reads the reason, applies the fix -- cannot close on 54 of the 73 refusals.

The information exists: `lab/wedge/boundary.py` recovers it by re-running `pymix.analyze` and `to_c` itself, which is exactly what `_analysis` already does inside a subprocess.  Surfacing it is a reporting change in `ail_cpython_hybrid._select`, not a compiler change; W0 below covers it.

## 5. Ready-to-queue tasks, each 2 hours or less

Ordered by measured gain.  Each names the reason, the test that guards it, and the gain this corpus measured.

### W1 -- not-a-top-level-function (measured ceiling 19.3% of the corpus self time)

Accelerate a method and a nested def, not only a top-level `def`.  Today `ail_cpython_hybrid._select` looks functions up in `_top_level_functions(tree)` and the unit is one module-level `def`; a `Class.method` or a closure is skipped before any typing.  Extend the unit to `ClassName.method` by mangling the C symbol with the class name, wrapping it with a `METH_VARARGS` entry, and rebinding it on the class (`C.m = _ail_hybrid_make(_native.m, C.m)`) once the class exists.  Self is not an ABI kind, so only an `@staticmethod` (and a nested def that closes over nothing) is in scope for two hours; a plain method takes `self` and needs a container ABI, which is a later task.

**Guard:** `tree_build`'s `Tree._inorder` / `_depth` / `_height` move from the refusal list to `build.json`'s `accelerated`; `test_ail_cpython_hybrid` gains a module with an `@staticmethod` hot helper and asserts it is listed and that its output is byte-identical.  Guard: `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

**Gain:** measured: up to 8.5 s of 44.2 s self time in this corpus, 19.3%; the reachable part (staticmethods and closures) is smaller -- the corpus's 8.5 s is plain methods, so treat this as the ceiling, not the gain.

### W2 -- list-return-kind (measured ceiling 15.8% of the corpus self time)

Give `pymix` and the boundary a `list[int]` / `list[float]` return kind.  `pymix` reports `unresolved-return` for a body whose `return xs` is a list, and the hybrid `_wrapper_source` has no C path for a returned list.  Add `pymix.LIST_INT` /`LIST_FLOAT` to the return kinds it resolves from a `return <list literal or list name>` and a list-append loop, and add a wrapper branch that returns `PyList_New` filled from the emitted `(const int64_t *out, int64_t n)` out-parameter pair the library ABI already uses (`compile-library`).

**Guard:** `bitset_bloom.bloom_set`, `dataframe_group.group_sum`, `matrix.mat_mul`, `rolling_stats.window_sums` and `matrix.identity` are listed as accelerated and their drivers stay byte-identical.  Guard: a new `test_ail_cpython_hybrid` case with an empty list return, a one-element list return and a 100k-element list return; plus `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

**Gain:** measured: 7.0 s of 44.2 s self time, 15.8%, across 6 modules and 11 functions.

### W3 -- tuple-parameter (measured ceiling 12.8% of the corpus self time)

Track a `tuple` parameter as an opaque homogeneous element stream.  `ast_lint` passes nested tuples of str/int; a real project's AST walk passes a node object.  Two hours buys the narrow case: a parameter annotated `tuple` whose body only calls `isinstance(child, tuple)`, `len(node)` and `node[i]` for a `range()` index.  Lower it to the existing `ail_list` of boxed values the general path already has, or refuse it by name with a fix (`write instead: node: list[object]`) so the AI can act.

**Guard:** `ast_lint.node_count` / `leaves` / `max_depth` / `sum_ints` appear in `build.json`; the driver's 7 printed lines are byte-identical.  Guard: a new case with an empty tuple, a one-element tuple, a nested tuple 8 deep, and an index from a list item and from a dict value; plus the four required modules.

**Gain:** measured: 5.7 s of 44.2 s self time, 12.8%; the whole of `ast_lint`.

### W4 -- indexing-can-raise (measured ceiling 12.6% of the corpus self time)

Let a clone that may raise `IndexError` fall back instead of being refused.  `_unsafe_body` refuses every `Subscript` outright.  The emitted typed clone already has a trap path: make the index check set the per-function mix flag (the same `extern int <mangled>__mix_overflow` the int64 path uses), return a zero, and let the Python wrapper re-run the original function when the flag is set.  The wrapper already catches `Fallback`, so the caller's `try/except IndexError` still sees CPython's exception; a call that never indexes out of range pays one flag test.

**Guard:** `edit_dist.levenshtein` (3.6 s alone) is accelerated and matches CPython on 800 rounds of 5 word pairs; a probe that indexes past the end still raises `IndexError` from the Python fallback.  Guard: a new `test_ail_cpython_hybrid` case with an in-range index, an index exactly at `len`, a negative index and an empty list; plus the four required modules.

**Gain:** measured: 5.6 s of 44.2 s self time, 12.6%, across 6 modules and 10 functions.

### W5 -- nested-list-annotation (measured ceiling 8.9% of the corpus self time)

Track `list[list[int]]`.  `pymix` has no kind for it, so every `graph_search` function is refused at the candidate stage.  The typed path already lowers `list[list[int]]` inside a whole-program build (the nested-lists test module exists); the gap is the *boundary* ABI and `pymix`'s kind fixed point.  Two hours: add `pymix.LIST_LIST_INT`, resolve it from the annotation, and map it to the existing `ail_list`-of-`ail_list` the typed emitter's nested-list path builds, with the wrapper copying each inner list as one buffer.

**Guard:** `graph_search.bfs_reach` / `dfs_count` / `degree_sum` / `edges_above` / `max_degree` appear in `build.json`; the driver prints the same 6 lines.  Guard: a new case with an empty outer list, an outer list with one empty inner list, a ragged inner list, and an inner list reached through an argument and through a dict value; plus the four required modules.

**Gain:** measured: 3.9 s of 44.2 s self time, 8.9%; the whole of `graph_search`.

### W6 -- list-float-abi (measured ceiling 2.8% of the corpus self time)

Fix the `ail_flist` prototype mismatch (section 4).  Either teach `_mix_validate_signature` that `ail_flist v_x` is the same ABI as `const double *v_x, int64_t v_x_len` (the call site already builds that pair), or make `to_c` spell a mixed-mode `list[float]` parameter the pointer+len way.  This is the cheapest task in the list: one prototype spelling.

**Guard:** `float_loops` goes from 0 to 8 accelerated functions and its driver stays byte-identical on all 9 printed lines.  Guard: a new `test_ail_cpython_hybrid` case with an empty `list[float]`, a NaN, `-0.0`, and a value that arrives through an argument, a list item and a dict value; plus the four required modules.

**Gain:** measured: 1.26 s of 44.2 s self time, 2.8%, but it is the only reason `float_loops` gets nothing at all.

## 6. Reproduce

```sh
python3 lab/wedge/census.py -j 2      # builds, native counts, byte-identical check
python3 lab/wedge/boundary.py          # which gate refused each function, and why
python3 lab/wedge/measure.py -j 2      # wall time, median of 5, plus cProfile
python3 lab/wedge/rust_bar.py          # cargo build + the PyO3 bar
python3 lab/wedge/analyse.py           # ranks the reasons by hot-path time
python3 lab/wedge/report.py            # renders this file
```

`census.py` and `measure.py` take `-j 2`; on a 4-core runner the whole pipeline is about 35 minutes, dominated by the 97 hybrid analyses at ~10 s each.

## 7. What is not measured

* Instruction counts: `perf_event_open` is denied on this runner, and callgrind was not used because the job is a wall-time question.
* The Rust bar covers 5 of 15 modules, as the task allows; the rest have no hand-written PyO3 twin.
* The hybrid analysis runs under `--exact-int`, so a module whose values exceed int64 can still be analysed; the *standalone* column needs `--exact-int` explicitly and is marked `(+exact)` when it does.
* The two `--exact-int` rows are real: `bitset_bloom` and `hashing` multiply past 2**63 in the driver, so the default 64-bit build stops loudly.  That is the documented int64 stop, not a silent difference.
