# job job-races2-11052147  started 2026-11-05T12:59:29Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Everything is committed on `job-races2-11052147` (not pushed, per the run rules).

## What changed

**Sub-step 1 — races.** races1 had already closed them: the baseline was silent races **0**. Nothing needed closing; I spent the time on sub-step 2.

**Sub-step 2 — more GIL-free shapes** (`typedpar.py`):
- `for i, v in enumerate(ex.map(f, xs[, ys]))` — lowered through the same item-order path as a direct `for`, binding the pair inside the loop.
- Futures submitted inside a `with` block and read after it (`futs`/`f[].result()`, named `f1.result()`). Previously this **failed to compile in both builds** (undefined name); unsupported uses now refuse by name and fall back to the lock.
- 5 new safe probes: `map_range`, `map_range_start`, `map_enumerate`, `futures_after_with`, `submit_after_with`.

**D4 built** (`ail_cpython_hybrid.py`): native calls with a list argument keep the GIL; scalar-only calls still release it. D1/D2/D3 written up as decisions in `RESULTS.md` (D1 stays refused; D2 fixed-order opt-in and D3 per-chunk append buffers are follow-ups).

## Numbers (full `lab/race/run.py`, both builds, `AIL_THREADS` 1/2/4/16 ×3)

| count | before | after |
|---|---|---|
| silent races | 0 | **0** |
| safe matched | 11/12 | **16/17** |
| safe GIL-free | 11/12 | **16/17** |

The one unmatched safe probe is `int_beyond_int64`: it stops loudly at int64 (its own note allows that) and remains the expected failure. TSan clean on all typed-parallel probes. 110 thread-free programs: `typedpar.rewrite_text` returns them byte-for-byte, so `program.c` hashes are unchanged (verified by rewrite identity; I did not rebuild a baseline copy).

## Tests run (final commit)

- `test_ail_race_probes` 31 tests OK (1 expected failure)
- `test_ail_typed_parallel` 16 OK (incl. TSan/ASan), `test_ail_threads` 18 OK
- `test_ail_parallel_for`, `test_ail_ffi_parallel`, `test_ail_cpython_hybrid`, `test_ail_examples_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: all OK
- `tools/update_manifest.py --check`: OK

## Probe results (`~/tools/cmp.sh`, plus 1/2/4/16 loops, both builds)

`e_empty`, `e_one`, `e_two_iter`, `e_arg`, `f_empty`, `f_twice`, `f_list_dict_value`, `f_exc_after`, `p_range_map`, `p_range_two`, `p_range_step`, `p_pool_range`, `p_submit_seq` — all match CPython. `f_bad_use` and `f_index_after` are refused by name and run under the lock.

Two things I did **not** do: no DEVLOG/DIFFERENCES edits (outside the allowed file list; no new semantic difference), and no PR/push. One pre-existing general-path difference surfaced: on a worker that raises, the general path loses the earlier map values CPython prints (probe `e_exc`); fixing it needs `threadlib`, outside this lane.
[commandcode stop=end_turn turns=99 out_tokens=75017]

## review 0
[model commandcode/deepseek-v4.1-flash]
Stopping here (39 min). Report:

## What the change really does

`typedpar.py`: (a) lowers `for i, v in enumerate(ex.map(f, xs[, ys]))` through the existing item-order map path (`enum=True` builds the `(idx, value)` pair); (b) adds `escape_uses`, which rewrites `.result()` / `for f in futs` reads of futures made in a `with` block in the rest of the enclosing statement list, plus a program-wide `left` check that refuses any remaining `Load` of a future name (fallback to the lock). `ail_cpython_hybrid.py`: suppresses `Py_BEGIN/END_ALLOW_THREADS` for wrappers whose parameters include a list. Plus docs, `RESULTS.md`, 5 race probes, 2 tests. No `parallel.py`/`pyfunc.py`/`cruntime.py` change. This matches the report.

## Probes (all in `/tmp/rprobes`, `bash ~/tools/cmp.sh … $PWD`, general + default build)

| probe | target | result |
|---|---|---|
| p_enum_start (enumerate start=10) | arg boundary | refused by name, CPython output |
| p_enum_value (`list(enumerate(map))`) | iterator as value | refused by name, match |
| p_enum_notuple (`for p in enumerate(map)`) | 1-tuple target | refused by name, match |
| p_enum_two (2 lists, unequal len) | min-length | typed, match |
| p_enum_rebind (body rebinds i,v; reads after) | mutation | typed, match |
| p_enum_empty (empty list) | empty | typed, match |
| q_enum_dict (iterable = dict value, arg) | arg/list item/dict value | typed, match |
| q_enum_neg (negatives) | sign | typed, match |
| p_fut_nested_if (with in `if`, read after) | nesting | typed, match |
| p_fut_module (module-level with, read after) | top-level escape | refused by name, match |
| p_fut_rebind (futs reassigned after) | aliasing/rebind | refused ("assigned more than once"), match |
| p_fut_two_groups, q_loop_with, q_in_and_out, q_fut_try | ordering | typed, match |
| q_fut_index (`futs[0].result()` after), q_fut_tuple, q_fut_ascomp, q_fut_append_loop | unrewritable shapes | refused by name, match |
| q_cross_fn (`futs` local in another function) | name scope | typed/fallback, match |

Thread sweep on `map_enumerate`, `futures_after_with`, `submit_after_with`: builds with **no refusal note**, `ail_par_run` present in `program.c`, stdout equal to CPython at `AIL_THREADS` 1/2/4/16.

Thread-free programs: rebuilt all 10 `lab/compare/src/*/typed.py` on `/tmp/base` and HEAD with `--debug-dir`; **10/10 `program.c` identical**. Not the 100 corpus programs (sampled only).

Hybrid: generated wrappers for int/str functions are byte-identical to base; only the `list[int]` wrapper lost its `Py_BEGIN/END_ALLOW_THREADS` pair. `_unsafe_body` rejects all subscripts, `len` of anything but a list/str parameter, and mutators — so a list parameter really is the only container an accelerated call can see; the claim holds.

Tests (`-j 2`): test_ail_typed_parallel, test_ail_cpython_hybrid, test_ail_race_probes, test_ail_safetynet — 4 modules, 0 failed (229 s).

## Report claims

- *races already 0* — consistent (no racy path touched); not re-measured. **Unverified by rerun.**
- *futures read after `with` previously failed to compile in both builds* — **verified** on `/tmp/base`: build exit 3, "name 'futs' is not defined" (both paths).
- *5 new safe probes on the typed path* — **verified** (`ail_par_run`, no refusal).
- *D4 built* — **verified** (diff, wrapper diff, test).
- *16/17 counts* — **unverified** (did not run `lab/race/run.py`); the 5 new probes exist and match.
- *110 thread-free hashes unchanged, verified by rewrite identity not by rebuild* — **verified for 10/10** compare programs rebuilt.
- *TSan clean* — not re-run separately; the TSan tests inside `test_ail_typed_parallel` passed.

## Pre-existing (not blocking)

- `multiprocessing.Pool` probes do not build in either path — identical on `/tmp/base`.
- The general path losing earlier map values when a worker raises (`e_exc`) — pre-existing, `threadlib`.

## Minor (non-blocking) notes

- `lab/race/run.py` now **hardcodes** "Baseline when this job started (races1): … 11 of 12" into every future `RESULTS.md` it generates; stale on the next run. It also splices `owner_decisions.md` in, duplicating the section now in `RESULTS.md`.
- The `left` check uses `p.made` accumulated over the whole program, so a future name reused as an unrelated local in another function forces a whole-program fallback to the lock. Conservative (still matches CPython), only a missed optimisation.

## Unverified

- `lab/race/run.py` counts before/after (silent races, 16/17) and TSan, not re-run.
- The 100 corpus programs in the hash check (10 sampled, identical).
- End-to-end `ail build --cpython` run of `hybrid_list_append` (wrapper C inspected and unit-tested only).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=35 out_tokens=35603]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T15:01:10Z
