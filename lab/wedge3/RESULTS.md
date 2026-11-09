# wedge3: the CPython hybrid on real pure-Python libraries with Rust rewrites

Branch `job-wedge3-11091201`, run 2026-11-09 on a 4-core GitHub Actions runner (Linux x86-64,
16 GB), CPython 3.12.3, PyPy 3.10+/3.11.17 (PyPy 8.0.1), gcc 13.3.0.  Measurement only: no
compiler or runtime file changed.

**Compiler used for every hybrid build:** the `job-obs5-op1109` worktree (the observed-type work
obs1-obs5 is not in the base tree), commit **`69e2dcd0a82580fa06e26b275352fbedfb7d31e1`**
(`obs5: full corpus measurement (hand and bare+obs)`).  It was fetched and checked out with
`git fetch origin job-obs5-op1109 && git worktree add ../obs5 FETCH_HEAD`; all builds use
`../obs5/AIL_CURRENT`.  `AIL_CURRENT` in this branch is not used by the measurements.

**Command note.**  This tree has no `ailc ext` command (the planned command is documented as
not existing in `DEVLOG.md`, 2026-11-08 aiknow1).  `ailc.py` forwards to `compile`, so the real
hybrid entry point is `python3 AIL_CURRENT/ail_chatgpt.py build --cpython SOURCE -o DIR`.

## Headline

On five real library pairs the hybrid made **0 of 191** hot-module functions native and ran at a
**geometric-mean 1.045x CPython** (range 0.967x-1.075x), while the same workloads run on the
rewritten libraries are a geometric-mean **2.31x faster** (rewrite/CPython 0.132x-3.277x per
pair, i.e. 7.58x faster to 3.28x slower); "compile it" today is a ~1.0x no-op against a
rewrite's ~2.3x, and the gap is not annotations -- observed kinds changed the native count by
exactly zero.

## 1. The pairs and the workloads

The libraries are pip-installed into throw-away venvs (`requirements.txt` pins the versions);
no library source is vendored.  For each pair a deterministic workload in `workloads/` runs
1.5-4.4 s on CPython.  `i` is the implementation selected by `WEDGE_IMPL` (`cpython`, `hybrid`,
`rust`); the PyPy column runs the same pure-Python library unchanged.

| pure Python | version | Rust/compiled rewrite | version | workload | hot modules built |
| --- | --- | --- | --- | --- | --- |
| networkx | 3.3 | rustworkx | 0.15.1 | 1200-node/80k-edge DiGraph, 100 Dijkstra + BFS sources | `algorithms/shortest_paths/{weighted,unweighted}.py` |
| jsonschema | 4.23.0 | jsonschema-rs | 0.26.0 | 40,000 documents against one draft-2020-12 schema | `_keywords.py`, `validators.py` |
| chardet | 5.2.0 | charset-normalizer | 3.4.0 | 600 byte payloads over six encodings | `universaldetector.py` |
| tomli | 2.0.2 | rtoml | 0.11.0 | 5,000 generated TOML documents | `_re.py`, `_parser.py` |
| difflib (stdlib) | 3.12 | rapidfuzz | 3.10.1 | 60,000 fuzzy pairs + 1,200 candidate lists | `difflib.py` |

For a hot module that uses relative imports, the temporary build copy rewrites only
`from .x import` / `from . import` to the absolute package spelling, so the analysis can run it as
a file; the measured source is otherwise byte-identical.  A generated module is loaded in place of
the library module by the workload.  The output of every workload is a deterministic digest.

## 2. Results (median of 5; seconds, wall clock)

`native` counts the functions `build.json` actually wrapped (top-level defs and, on obs5, methods).
`funcs` is every function the build considered in the built modules.  Ratios below 1.0 mean the
hybrid is faster than the column; `h/C`, `h/P`, `h/R` are hybrid/CPython, hybrid/PyPy, hybrid/Rust.

| library | funcs | native | CPython | PyPy 3.11 | hybrid | Rust rewrite | h/C | h/P | h/R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| networkx | 41 | 0 | 4.029 | 3.223 | 3.897 | 1.449 | 0.967 | 1.209 | 2.690 |
| jsonschema | 61 | 0 | 1.999 | 2.105 | 2.094 | 0.264 | 1.048 | 0.995 | 7.941 |
| chardet | 7 | 0 | 1.503 | 1.062 | 1.615 | 4.925 | 1.075 | 1.521 | 0.328 |
| tomli | 38 | 0 | 1.827 | 1.028 | 1.941 | 0.561 | 1.063 | 1.889 | 3.459 |
| difflib | 44 | 0 | 2.613 | 1.082 | 2.807 | 0.828 | 1.075 | 2.595 | 3.390 |
| **total/geomean** | **191** | **0** | | | | | **1.045** | **1.551** | **2.415** |

The networkx row is a 7-rep re-run (the 5-rep run's observed-hybrid column was an outlier); the
others are medians of 5.  Wall-clock medians on this shared runner vary by ±10-15%; the plain
hybrid column was 0.967-1.075x CPython on every pair in every run.

**Correctness:** every hybrid build (plain and observed) matched CPython's stdout byte for byte on
all five workloads, and PyPy matched CPython on all five.  The Rust rewrite matched CPython for
networkx, jsonschema and tomli; chardet and difflib use a different metric/detector and do not
claim equality (see section 5).

## 3. Hybrid with and without observed kinds

Each workload was run once under `AIL_CURRENT/ail_observe.py run --all --fast`; `annotate` then
wrote every observed monomorphic parameter/return kind back into the hot module (existing
annotations kept), and the same hybrid was rebuilt from the annotated copy.  The recorded kinds
changed the source for networkx, jsonschema and difflib; for tomli and chardet no observed
kind was expressible (tuples/dicts/user classes), so the files are unchanged.  **In every case the
native count stayed 0.**

| library | native (plain / observed) | CPython | hybrid plain | hybrid + observed | obs/C |
| --- | ---: | ---: | ---: | ---: | ---: |
| networkx | 0 / 0 | 4.029 | 3.897 | 4.519 | 1.122 |
| jsonschema | 0 / 0 | 1.999 | 2.094 | 2.086 | 1.044 |
| chardet | 0 / 0 | 1.503 | 1.615 | 1.608 | 1.070 |
| tomli | 0 / 0 | 1.827 | 1.941 | 1.943 | 1.063 |
| difflib | 0 / 0 | 2.613 | 2.807 | 2.779 | 1.064 |

Observed kinds recover the annotation text (they are what `ail_observe annotate` is for) but they
do not lift a single real-library function over the selection gates; the blockers are structural,
not missing annotations.  This is the direct real-library answer to the obs1 corpus result.

## 4. Refusal reasons, ranked by the CPython time they keep

Method: the recorder's per-function `self_s` (1 ms SIGPROF sampler), summed over functions defined
in a built hot module, charged to the reason `build.json` gives for that function (or to a nested
marker when the build never considered it).  The base is **9.58 s** of sampled self time across the
built modules; 0 s is native.  Shares are of that sampled base (cProfile/recorder time ranks the
functions; it is not wall time).

| # | reason | self s | share | functions | example functions |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | `pymix`: not a typed candidate (parameter/return kind not expressible: graph object, dict/tuple, validator, regex match) | 4.08 | 42.6% | 108 | `_dijkstra_multisource`, `_weight_function`, `parse_value`, `type`, `_single_shortest_path_length` |
| 2 | nested function / lambda / comprehension (not a top-level def or method unit) | 3.51 | 36.7% | 8 | `_weight_function.<locals>.<lambda>` (2.6 s), `create.<locals>.Validator.descend/evolve/__attrs_post_init__` (0.80 s), `SequenceMatcher.ratio.<locals>.<genexpr>` |
| 3 | method: class shape (bases, metaclass, decorators or class attributes) | 1.89 | 19.7% | 18 | `UniversalDetector.feed/close`, `SequenceMatcher.find_longest_match/ratio`, `Flags.set` |
| 4 | method: dunder / decorated / non-plain signature | 0.084 | 0.9% | 5 | `NestedDict.__init__`, `Differ.__init__` |
| 5 | method: calls a method that stays in CPython | 0.009 | 0.1% | 1 | `Differ._fancy_helper` |
| | module body | 0.001 | 0.0% | 3 | `<module>` |
| | **outside the built hot modules** | **2.14** | | | chardet probers (1.54 s), jsonschema `_utils`/`_types`/`exceptions` (0.46 s), networkx `digraph`/`backends` (0.16 s) |

The last row is not a selection gate: it is the library code in modules this job did not copy and
build.  It matters for the headline -- for chardet the class `universaldetector` is only 0.016 s of
the workload; the per-byte work lives in `charsetprober`, `sbcharsetprober`, `codingstatemachine`,
`chardistribution` and the script probers.  Even a perfect result on the one built module could
not move chardet.

The two dominant reasons are exactly the ones wedge1 found on self-written code: the unit is still
a top-level `def`/plain method, and `pymix` still cannot express a container or user-object
parameter/return.  Methods are now *listed* (obs4) and can be native for scalar fields, but no
real hot method met the class-shape rule.

## 5. Two-hour tasks for the top five reasons

1. **Nested function / lambda unit (measured 3.51 s).**  Promote a closure with no free variables
   (a nested `def`/`lambda` that only reads its parameters and module constants) to a normal unit:
   in `ail_cpython_hybrid._analysis`, collect `ast.Lambda` and `FunctionDef` nodes with
   `__qualname__` containing `<locals>`, prove no `nonlocal`/free-variable capture, emit them under
   their own mangled name, and run the existing `_select` fixed point.  Guard: a hybrid test with
   `def outer(): def inner(x: int) -> int: ...`, a module-level `key = lambda w: w`, and a
   comprehension-free list return; stdout must match CPython and `build.json` must list the nested
   name.  Expected: networkx's 2.6 s lambda and jsonschema's 0.80 s attrs-generated `Validator`
   methods become selectable (they may still hit the class-shape gate, which is task 3).

2. **Name the `pymix` refusal and seed one new kind (measured 4.08 s).**  Today 108 functions get
   the single opaque line "not a typed candidate".  In the analysis subprocess, capture
   `pymix`'s per-function rejection (it already produces the facts) and write it under
   `build.json:rejected[name].detail`; then add exactly one observed kind, the most common one in
   these modules, `dict[str, int|str]` parameters/returns, guarded by the same entry checks as
   `list[int]` (fresh copy, every key/value checked, fallback on a different shape).  Guard: a
   hybrid test where a `dict[str, int]` parameter reaches the function through an argument, a list
   item, an attribute and a dict value, plus a non-matching dict that must fall back; `test_ail_cpython_hybrid`.
   Expected: names 42.6% of the refused time and makes the largest sub-kind actionable.

3. **Methods whose class has class attributes or a plain object base (measured 1.89 s).**  Relax
   the class-shape gate for `class C:` with `__bases__ == (object,)` (or no explicit base) when
   every class-level name the method reads is a literal/`re.compile` constant and every `self`
   field is a scalar already written by `__init__`: inline the constants into the emission and
   guard each `self.attr` read against the instance `__dict__`; fall back on any other attribute.
   Guard: a hybrid test on a class with `MINIMUM_THRESHOLD = 0.20` and an int field, plus a
   subclass with an overridden attribute that must stay in CPython.  Expected: `chardet`'s
   `UniversalDetector` methods and `difflib`'s `SequenceMatcher` methods become selectable
   (1.7 s + 0.02 s of profiled time), still subject to the call/index body gates.

4. **Plain `__init__` methods with scalar fields (measured 0.084 s).**  Admit a dunder `__init__`
   whose body only assigns scalar attributes to `self` (the same write-back already added behind
   `AIL_HYBRID_FIELD_STORES=1`, but for construction) and return `None`; keep every other dunder
   refused.  Guard: a hybrid test constructing 10,000 instances and checking the scalar fields,
   plus `__init__` that appends to a list (must be refused).  Expected: `NestedDict`, `Differ`,
   `_RefResolver` constructors become native; small by itself, a prerequisite for task 3.

5. **Reclaim a method when its callee becomes native (measured 0.009 s).**  The obs4 fixed point
   already re-evaluates a caller after a callee is chosen; make the refusal message name the
   unresolved callee chain and re-run selection in dependency order until no new method is added.
   Guard: two methods where only the second is independently selectable, asserting the first is
   reclaimed in the same build; `test_ail_cpython_hybrid`.  Expected: removes the last reported
   "calls a refused method" bucket (0.009 s) and makes task 3's class-method wins propagate.

## 6. Probes and self-check

No compiler behaviour changed in this job, so the `cmp.sh` probe rule applies to the artefacts:
the hybrid was checked against CPython on every workload (section 2), and small boundary probes
were run on both the workload and a toy module:

| probe | what it covers | result |
| --- | --- | --- |
| `networkx_bench.py` | int graph weights, distances through a dict/list-returning algorithm | CPython = hybrid = obs-hybrid; PyPy = CPython |
| `jsonschema_bench.py` | values reaching validation through a dict item and a list item | CPython = hybrid = obs-hybrid; PyPy = CPython |
| `chardet_bench.py` | bytes argument, detector state across `feed` calls | CPython = hybrid = obs-hybrid; PyPy = CPython |
| `tomli_bench.py` | str input, nested tables/arrays, float and int returns | CPython = hybrid = obs-hybrid; PyPy = CPython |
| `difflib_bench.py` | str/list arguments, list return from `get_close_matches` | CPython = hybrid = obs-hybrid; PyPy = CPython |
| `/tmp/probes/wedge3_int.py`, `wedge3_list.py`, `wedge3_str.py` | int64, `list[int]` parameter/return, `str` return | `bash ~/tools/cmp.sh` g/d same stdout; hybrid build byte-identical |

All hybrid outputs are byte-identical to CPython; there is no silent difference to report, so no
new `DIFFERENCES.md` row was needed.

## 7. Limitations, stated plainly

* The Rust/compiled column is the library's own rewrite on the same input.  For chardet,
  charset-normalizer is a *different, more expensive* detector and is 3.3x slower than chardet on
  these payloads; it is reported as measured, not hidden.  For difflib, rapidfuzz computes the
  related indel ratio, which agrees with difflib on 88% of random pairs but is not the same metric,
  so only the hybrid-to-CPython equality is claimed.
* Only the hot modules listed in section 1 were built.  chardet's probers and jsonschema's
  `_utils`/`_types` are outside that set; section 4 quantifies their time (2.14 s) rather than
  pretending the built-module base is the whole workload.
* Wall-clock medians on a shared runner move by ±10-15%; the observed-hybrid column is within that
  noise on all pairs except the networkx 5-rep outlier, which was re-run.
* The `--all --fast` recorder samples container elements and stops exact call counting after its
  budget, so the refusal shares rank functions and do not add up to wall time.
