# FRONTEND_SPEED — where AIL's Python front end spends compile time, and how to cut it

Status: measurement + design only. No compiler change (`docs/design` and `lab/fe`).
Measurement: [`lab/fe/RESULTS.md`](../../lab/fe/RESULTS.md), harness `lab/fe/prof.py`, raw data
`lab/fe/results.json`.

## The problem

tcc1 (`lab/tcc/RESULTS.md`) made the C compile **121x** faster and the cold edit-run only **1.6x**
faster, because the Python front end is the fixed cost. vibe1 (`lab/vibe/RESULTS.md`) measured the
write-run loop at **111 s** for AIL against **1 s** for CPython. AIL is aimed at vibe coding, so the
edit-run loop is the product, not the C compiler alone.

This document answers two questions with numbers: what share of a cold build is the Python front
end (and inside it, which passes and functions), and which options can remove that share.

## What the measurement says

On the ten `lab/compare/src/*/main.py`, their ten `typed.py`, and the twelve `corpus/gdev`
programs timed in tcc1 (32 programs; the full table is in `lab/fe/RESULTS.md`), the cold wall splits
as follows. Times are medians of 3 cold runs with a fresh `AIL_CACHE` and `TMPDIR`.

| phase | seconds | share of wall |
|---|---:|---:|
| interpreter start + imports (outer + inner) | 3.05 | 0.8% |
| source load / merge (`_load_sources`) | 10.82 | 3.0% |
| cheap refusal passes | 0.74 | 0.2% |
| typed emitter (`pyfunc.to_c`: analysis + C text) | 73.71 | 20.3% |
| general emitter (`pyboxed2.build`: analysis + C text) | 109.67 | 30.1% |
| **Python front end, total** | **197.98** | **54.4%** |
| C compile + link (`gcc`) | 118.62 | 32.6% |
| other (the second `check`, plus spawn/copy/waits) | 46.67 | 12.8% |
| **wall** | **363.97** | 100% |

`typed`/`general` are each reported whole because both emitters interleave type analysis with
writing the C string. Splitting "analysis" from "C emission" would need a compiler change, which
this job forbids.

The share that matters for every option below is **the front end's share of the wall** (the
`Amdahl` baseline) and, within it, the emitter share and the top-20 function share:

| quantity | value | where it comes from |
|---|---:|---|
| front end share of cold wall (`F/W`) | 54.4% | `RESULTS.md` §1 |
| emitter share (`E/W`) | 50.4% | `RESULTS.md` §1 |
| C compile + link share | 32.6% | `RESULTS.md` §1 |
| interpreter + import share (`I/W`) | 0.8% | `RESULTS.md` §1 |
| failed typed attempt on general-path programs | 26.55 s = 7.3% of all wall (9.2% of the general-path wall) | `RESULTS.md` §1 |
| second `check` for the fallback note (`other` bucket) | 46.67 s = 12.8% (25.2% of `ticket_audit`, 11.2% of `scar_life`) | `RESULTS.md` §1 |
| top-20 functions' share of wall (cProfile) | 30.7% | `RESULTS.md` §2 |
| … of which AST walking (`fastwalk.walk`, `ast.iter_*`, `_walk_uncached`) | 15.8% | `RESULTS.md` §2 |
| … of which type queries (`_etype`, `_is_str_expr`, `_is_slist_expr`, …) | 6.0% | `RESULTS.md` §2 |
| warm (whole-build cache hit) wall, fast programs | 0.47 s median (cold 3.63 s, 7.8x) | `RESULTS.md` §3 |
| warm wall on fallback programs (still paying `check`) | 12.3 s `scar_life`, 25.5 s `ticket_audit` | `RESULTS.md` §3 |

Key facts for the design:

* **The front end is the majority of a cold build**, and on `berth_sim` it is 88% of the wall —
  exactly the kind of program where tcc1 got no speedup. On the C-dominated programs (`g17_004`,
  `g04_006`, `g10_010`) gcc is 40–47% and tcc could halve them.
* **The typed and general emitters are almost all of the front end** (50.4% of wall of 54.4%).
  Parsing, refusals and source loading are small (3.2% together). A win has to come from the
  emitter, not from the cheap passes.
* **The failed typed attempt is worth 7.3% of all wall**, but it is concentrated: 8 of the 14
  general-path programs enter `to_c` and fall back, and two of them dominate — `ticket_audit`
  18.58 s (19.4% of that build) and `scar_life` 6.16 s (6.4%). The other 6 general-path programs
  are refused by a cheap pre-pass before the emitter. A "decide fallback from a pre-scan" option is
  therefore worth a real but bounded 7.3%, and 19.4% on the program that resembles a real app.
* **The top-20 functions are a large, addressable slice** (30.7% of wall) of the front end, and two
  families dominate: repeated AST walks (`fastwalk.walk` alone is 9.9% of wall, 81.8 M calls; the
  walk family 15.8% including `ast.iter_child_nodes`/`iter_fields`/`_walk_uncached`) and the
  memoised type queries (`_etype` and friends, 6.0%, plus the `_query_memo` wrapper 0.9%).
* **A whole-build cache hit already removes the front end** (`docs/design/FE_CACHE.md`,
  `AIL_SERVER`): the fast programs go 3.63 s cold → 0.47 s warm. But the residual includes a
  second full front end on fallback programs: `compile` spawns `ail_chatgpt.py check` to position
  its advisory `note: … built on the general path` line (`_fallback_notes` → `_locate_refusal`),
  which is 12.8% of cold wall and leaves `scar_life` at 12.3 s and `ticket_audit` at 25.5 s **warm**.
  That is the single cheapest measured win in this report.

## Options, ranked by measured Amdahl bound

The bound is the largest wall reduction the option can give on the measured workload if its
component went to zero (cold build, cache miss), computed from `RESULTS.md`, not guessed. "Edit
bound" is the same number, because an edit misses the whole-source key and therefore pays a cold
front end. `x` is the wall speedup implied by that share, `1/(1-share)`.

| # | option | measured share | Amdahl bound (cold / edit) | wall speedup | risk | files |
|---:|---|---:|---:|---:|---|---|
| 1 | Per-function analysis cache across edits | emitter share `E/W` = 50.4% | 50.4% | 2.02x | high | `pyc.py`, `pyfunc.py`, `pyboxed2.py`, `buildcache.py`, `fecache.py` |
| 2 | Compile the front end (mypyc / Cython) | `F/W` = 54.4%; k=2.5 | 32.6% | 1.48x | medium-high | `pyproject.toml`, `packaging/`, new build target |
| 3 | Algorithmic fixes in the top-20 hot functions | 30.7% (walk 15.8%, queries 6.0%) | 30.7% | 1.44x | low | `fastwalk.py`, `pyfunc.py`, `pyboxed2.py`, `optlib.py`, `unified*.py` |
| 4 | Drop the second `check` that positions the fallback note | `other` = 12.8% | 12.8% | 1.15x | low | `ail_chatgpt.py` |
| 5 | Skip the doomed typed attempt from a pre-scan | 7.3% | 7.3% | 1.08x | low | `pyc._refuse_big_capable`, `pyc.build` |
| 6 | Long-lived compile server (`ail run`) | 0.8% cold; 58% of the 0.47 s warm residual | 0.8% cold / 58% warm | 1.008x cold, 2.4x warm | medium | `ail_server.py`, `ail_chatgpt.py`, `pyc.py` |
| 7 | Lazy imports | 0.8% cold; 5.5% of a warm hit | 0.8% cold | 1.008x cold | low | `ail_chatgpt.py`, `pyc.py`, `pyfront.py` |

Options 2 and 3 overlap (a compiled front end speeds up the same hot functions but does not make
the repeated walks disappear); their bounds are alternatives, not additive. Option 4 is outside the
brief's six; it fell out of the measurement of the `other` bucket and is ranked because it is the
cheapest real win.

### 1. Per-function analysis cache across edits — the largest measured share

Measured share: the emitter, `E/W` = 50.4% of cold wall (73.71 s typed + 109.67 s general of 363.97 s).
If only the function whose source changed is re-analysed, the bound is the whole emitter share
(2.02x wall); on a typical edit one of N functions changes, so the realistic bound is
`E/W x (N-1)/N`.

Risk: **high**. Both emitters do whole-program, interprocedural inference (`pyfunc.to_c` infers
across functions and modules; `pyboxed2.build` builds module tables and reachability). A function's
result is only reusable if every fact it read is unchanged — its own source, the signatures and
inferred types it consumes, and the module-level constants it reads. Getting the dependency key
wrong produces wrong C silently, which is the one outcome the project forbids.

Files touched: `pyc.py` (`_build_unshadowed`, `build_cached`), `pyfunc.py` (`to_c`, the function
loop), `pyboxed2.py` (`build`), `buildcache.py` / `fecache.py` (a per-function key and store).

Equality proof: build the whole corpus twice with the cache off and on (a) from scratch and (b)
after touching one function body; the C the compiler sees must be **byte-identical** to the
uncached build, including the fallback note. The existing `lab/fecache/verify.py` compares the
exact C the compiler was handed; reuse it and add the edit case.

### 2. Algorithmic fixes in the top-20 hot functions — the safest large share

Measured share: the top-20 functions' self time is 30.7% of the profiled wall; AST walking is 15.8%
and the type queries 6.0%. Removing (or memoising per analysis epoch) the repeated walks in the
fixed-point and per-function rounds attacks the single largest call count (`fastwalk.walk` is
81.8 M calls across the sample; `pyfunc.py` alone has ~395 `ast.walk(` call sites). A 50% cut of the
walk family is a 7.9% wall win on its own (1.09x).

Risk: **low**. These are pure computations over the AST and the query cache; the node order and
results can be pinned. The project already has the pattern: `fastwalk.py` replaced `ast.walk`
behind `AIL_FASTWALK`, and `_query_memo` caches `_etype` and friends behind `AIL_QUERY_CACHE`.

Files touched: `fastwalk.py` (a per-node children index or a per-body walk memo keyed by the
analysis epoch), `pyfunc.py` (call the memo instead of re-walking in the fixed-point rounds; flatten
`_query_memo`'s key), `pyboxed2.py`, `optlib.py`, `unified*.py`.

Equality proof: `test_ail_frontend_speed` already asserts `fastwalk.walk` yields exactly the
standard library's nodes and that `AIL_QUERY_CACHE=0` generates byte-identical C. Extend it to the
new memo and diff the generated C over the whole corpus with the option on and off.

### 3. Compile the front end itself (mypyc / Cython) — the biggest absolute share

Measured share: the front end is `F/W` = 54.4% of cold wall; with a conservative 2.5x on the
pure-Python front end the bound is `(F/W)(1-1/2.5)` = 32.6% (1.48x wall; 1.57x at k=3, 1.37x at
k=2). On `berth_sim` that is 9.89 s → ~5.3 s even before the C compile.

Risk: **medium-high**. The front end is ~60k lines (`pyfunc.py` 43.7k, `pyboxed2.py` 13.9k) of
CPython-dependent code: big integers in the constant folder, `ast` mutation, `copy.deepcopy`,
exceptions with `source_line`, and a large import graph. mypyc supports these but the build and the
wheel change, and debugging a compiled compiler is harder. Cython has the same shape and more
per-file work.

Files touched: `pyproject.toml` (a second build path or a `[tool.mypyc]` section), `packaging/`
(the wheel backend must ship the compiled modules and keep the `.py` fallback), a CI job that runs
the corpus on both. No compiler semantics change.

Equality proof: the compiled front end is a drop-in: on the corpus the generated C must be
byte-identical to the pure-Python front end's, and `test_ail_frontend_speed`, `test_ail_safetynet`
and `test_ail_corpus_findings3` must pass on both. `tools/wheel_same_c.py` already compares the C
the wheel produces.

### 4. Drop the second `check` that positions the fallback note — the cheapest win

Measured share: `other` is 12.8% of cold wall (46.67 s); on `ticket_audit` it is 23.80 s of 94.42 s
(25.2%) and on `scar_life` 10.94 s of 97.38 s (11.2%). The measurement showed it is not process
spawn: after a general-path build, `compile` calls `_fallback_notes` → `_locate_refusal`
(`ail_chatgpt.py:5499`, `:5995`), which starts a second `ail_chatgpt.py check` over the whole source
to put a line:col on the advisory `note: … built on the general path` line. That second process
runs the front end again. It is also paid on a **cache hit**, because the note comes from the cached
stderr: `scar_life` warm is 12.3 s and `ticket_audit` warm is 25.5 s, not the 0.47 s a hit costs
elsewhere.

Risk: **low**. The note is advisory; stdout and the exit status never depend on it.
`AIL_QUIET_FALLBACK=1` already skips the whole subprocess. The fix is to drop the re-check by
default (print the note without a position, or keep `AIL_FALLBACK_LOCATE=1` as the opt-in), so the
only observable change is the absence of `path:line:col` on a `note:` line.

Files touched: `ail_chatgpt.py` (`_fallback_notes`, `_locate_refusal`), possibly `pyc.py` to carry
the already-known position in the cached metadata.

Equality proof: generated C must be byte-identical on the corpus; stderr is expected to differ only
by the position on the note line (record the exact diff). `test_ail_fallback_note` pins the note
wording.

### 5. Long-lived compile server — removes the fixed per-invocation cost

Measured share: on a cold build only the interpreter+import share, `I/W` = 0.8%. On a fast warm hit
(0.47 s) the outer import is 0.026 s (5.5%), `_load_sources` 0.193 s (41%) and the key hash 0.055 s
(12%): a server that already holds the source and the key could remove about 58% of that residual,
though the absolute saving is ~0.27 s per invocation. The server also keeps the parsed AST and
analysis warm across requests, which overlaps option 1. A server already exists (`AIL_SERVER`,
`ail_server.py`); `docs/design/FE_CACHE.md` measured a hit path of 0.72 s for berth_sim with the
server and the `cc` cache on. The remaining win is on the **edit** path: today a one-function edit
still pays the whole front end in a fresh process.

Risk: **medium**. State must be keyed by the exact merged source, compiler sources, environment and
toolchain (the current `fe` key does this); a stale cache is a silent wrong answer. Concurrency and
memory growth need caps.

Files touched: `ail_server.py`, `ail_chatgpt.py` (the client), `pyc.py` (a request that accepts the
merged source instead of a temp file), `fecache.py`.

Equality proof: server on vs off must produce byte-identical C on the corpus and on the edit case;
the existing `test_ail_server` and `test_ail_fe_cache` cover the keying.

### 6. Lazy imports — small on a cold build, visible on a warm hit

Measured share: `I/W` = 0.8% on a cold build; `importtime` shows the two entry points cost 0.039 s
and 0.081 s, and the outer import is 0.026 s of a 0.47 s warm hit (5.5% there). The inner compiler
(`pyc.py`) imports the whole `pkg-v12` graph before it knows whether the build will hit the cache.

Risk: **low**. Moving imports into the functions that use them cannot change output; the only risk
is a missed import on a cold path, caught by the corpus.

Files touched: `ail_chatgpt.py`, `pyc.py`, `pyfront.py`.

Equality proof: byte-identical C on the corpus; `python3 -X importtime` before/after; the warm hit
must not regress.

### 7. Skip the doomed typed attempt from a cheap pre-scan — measured, concentrated

Measured share: the failed typed attempt is 26.55 s of 363.97 s (7.3% of all cold wall; 9.2% of the
general-path wall). It is concentrated: `ticket_audit` 18.58 s (19.4% of that build) and
`scar_life` 6.16 s (6.4%) are most of it; `ledger_bin` 0.33 s; the corpus programs 0.01–0.40 s. Six
of the 14 general-path programs are already refused by the cheap passes before the emitter
(`chain_relax`, `rail_transfer`, `term_rank`, `g17_004`, `g14_014`, `g14_004`), so their typed
attempt is ~0.

Risk: **low** if the pre-scan only moves an existing refusal earlier; **medium** if it tries to
predict a refusal the emitter would otherwise discover, because a wrong prediction changes the
error message or the path. Keep it to a reordering of existing, proven passes.

Files touched: `pyc.build`, `pyc._build_unshadowed`.

Equality proof: byte-identical C and the same stderr on the corpus; the refusal wording is pinned by
`test_ail_refusal_messages` and `test_ail_typed_blockers`.

### Ranking, in one line

Per-function cache (50.4%) > front-end mypyc (32.6%) > hot-function fixes (30.7%) > drop the note
check (12.8%) > typed pre-scan (7.3%) > server (0.8% cold, 58% of the 0.47 s warm residual) > lazy
imports (0.8%).

## Chosen top three and the task split

Ranked strictly by measured share, the board is per-function cache, mypyc, hot-function fixes. The
note check (12.8%) is queued first anyway: it is nearly free, it also fixes the warm path for
fallback programs, and every later measurement gets cleaner once it is gone.

1. **Drop the second `check` for the fallback note** (option 4) — 12.8% for near-zero risk.
2. **Hot-function algorithmic fixes** (option 3) — 30.7%, lowest risk of the big levers.
3. **Front-end compilation with mypyc** (option 2) — 32.6%, independent of option 3 and multiplies
   whatever option 3 leaves.
4. **Per-function analysis cache** (option 1) — 50.4%, the largest bound, but it needs the
   dependency key right; split into small, independently shippable steps.

Each step is at most two hours and is written to be queued as a task.

### Task FE-SPEED-A0 — stop re-running `check` to position the fallback note

Files: `AIL_CURRENT/ail_chatgpt.py` (`_fallback_notes`, `_locate_refusal`).
Do not spawn `check` by default. Print the advisory `note: … built on the general path` line without
a position, or carry the position the compiler already knows in the cached stderr/metadata. Keep
the old behaviour behind `AIL_FALLBACK_LOCATE=1`.
Test: `test_ail_fallback_note`; build `ticket_audit`, `scar_life`, `ledger_bin` and diff the
generated C byte for byte; diff stderr (only the note's position may be missing).
Number: `ticket_audit` cold 94.4 s → ≤71 s (its 23.8 s `other`) and warm 25.5 s → ≤1.7 s;
`scar_life` cold 97.4 s → ≤86 s; no other program changes.

### Task FE-SPEED-A1 — memoise repeated AST walks per analysis epoch

Files: `AIL_CURRENT/python/pkg-v12/fastwalk.py`, `pyfunc.py`, `unified.py`.
Add `fastwalk.nodes(root, epoch)` returning the same breadth-first list as `walk` and cached by
`(id(root), epoch)` in a dict cleared on the same epoch bump that clears the query cache
(`_EPOCH` in `pyfunc.py`). Replace the hot `list(ast.walk(body))` loops in `pyfunc.to_c` and the
fixed-point rounds with it. Keep `AIL_FASTWALK` as the off switch.
Test: extend `test_ail_frontend_speed` to assert the memo returns exactly `ast.walk`'s nodes and
that `AIL_FASTWALK=0` still produces byte-identical C; diff the C over the corpus.
Number: reduce the top-20 `fastwalk.walk` + `ast.iter_*` self time by at least 40% on `berth_sim`
(cProfile), with no change to the generated C.

### Task FE-SPEED-A2 — flatten the type-query cache and cut its key cost

Files: `AIL_CURRENT/python/pkg-v12/pyfunc.py`.
`_query_memo` currently builds a `(tag, id(node), id(ctx))` tuple and goes through a Python closure
for every query (it is itself in the top-20). Inline the fast path: one dict lookup on
`(id(node), id(ctx))` per tag, no tuple allocation, no `getattr(ctx, '_qc_uncacheable')` on the hot
path (read a cached module global bumped with the epoch). Keep `AIL_QUERY_CACHE=verify` and `=0`.
Test: `test_ail_frontend_speed` (`AIL_QUERY_CACHE=0` byte-identical C), `test_ail_query_cache` if
present; diff the corpus.
Number: cut the `_query_memo` wrapper self time by at least 30% and total cold wall on `berth_sim`
by at least 5%.

### Task FE-SPEED-A3 — remove repeated per-function walks in the general emitter

Files: `AIL_CURRENT/python/pkg-v12/pyboxed2.py`, `optlib.py`.
`pyboxed2.build` derives the same function-body facts in several passes; compute the node lists and
`_own_node_ids`/`_assign_target_names` once per function and pass them down.
Test: byte-identical C over the corpus (`AIL_UNIFIED_FORCE=1` and default); `test_ail_unified`,
`test_ail_safetynet`.
Number: reduce the general emitter's time on `ledger_bin` and `rail_transfer` by at least 10%
(timed wrapper), no C change.

### Task FE-SPEED-B1 — build the front end with mypyc, keep the .py fallback

Files: `pyproject.toml`, `packaging/ail_wheel_backend.py`, `packaging/ail_lang/`, a new
`tools/mypyc_build.py`, `.github/workflows/`.
Add a `mypyc` build of `python/pkg-v12/*.py` into extension modules shipped in the wheel; if the
extension import fails, fall back to the `.py` sources. CI builds both and runs the corpus.
Test: `tools/wheel_same_c.py` (byte-identical C from the wheel), `test_ail_packaging`,
`test_ail_frontend_speed`.
Number: at least 2x on the front-end share of `berth_sim` (8.72 s → ≤4.4 s; wall 9.89 s → ≤5.6 s),
identical C.

### Task FE-SPEED-B2 — run the compiler source under the compiled front end in-tree

Files: `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/python/pkg-v12/__init__.py` or an import shim.
Prefer the compiled modules when present in a checkout (not only in the wheel), behind
`AIL_COMPILED_FE=1`, so `lab/fe/prof.py` can measure it and CI can compare.
Test: corpus byte-identical C with the flag on/off; `test_ail_frontend_speed`, `test_ail_safetynet`.
Number: state the measured mypyc speedup on the `lab/fe` sample, same C.

### Task FE-SPEED-C1 — per-function cache key and hit path for the general path

Files: `AIL_CURRENT/python/pkg-v12/pyc.py`, `pyboxed2.py`, `fecache.py`, `buildcache.py`.
Define a per-function key: the function's normalized source, the facts it read (module constants,
callee signatures and inferred kinds), and the emitter mode. Cache the emitted C for one function
and splice it into the module. Start with `pyboxed2` (the general path), where function bodies are
lowered more independently.
Test: new `test_ail_fe_function_cache`; build a two-function program, edit one, assert the untouched
function's C is reused and the whole C is byte-identical to an uncached build; run the corpus twice
(cold, then edit one function) and diff.
Number: on an edit of one function in a two-function program, cut front-end time by at least 30%;
no C difference.

### Task FE-SPEED-C2 — per-function cache for the typed path

Files: `AIL_CURRENT/python/pkg-v12/pyfunc.py`, `pyc.py`.
Extend the key from C1 to the typed emitter; refuse the cache (fall back to a full build) whenever a
function reads a fact the key cannot prove stable — the same conservative rule the big-int gates
use. No silent reuse.
Test: extend `test_ail_fe_function_cache`; `test_ail_safetynet`, `test_ail_corpus_findings3`, the
whole corpus with the cache on and off.
Number: same as C1 on the typed programs; zero C differences over the corpus.

### Task FE-SPEED-C3 — wire the cache into the server and the edit loop

Files: `AIL_CURRENT/ail_server.py`, `ail_chatgpt.py`, `fecache.py`.
Have the resident server keep the per-function cache warm across requests and key the request by
the merged source; expose `ail run` so a reprocessed file reuses the server.
Test: `test_ail_server`, `test_ail_fe_cache`, the C1/C2 corpus diff with the server on.
Number: a one-function edit in the two-function program completes in at most the C compile time
plus the changed function's front-end time; measure before/after.
