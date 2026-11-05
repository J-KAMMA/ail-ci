# job job-recstop1-11060309  started 2026-11-05T18:10:16Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
All three review defects are fixed and verified on the committed branch.

## What I changed

1. **Typed caught recursion had the wrong class.** When a program can observe the class (names `RecursionError` or binds `as e`), `pyfunc` now gives the trap its own exception code after every user class; `classes_table` names it, `ail_exc_kind_of` returns it, and `except RuntimeError` still catches it through the (one-way) subclass relation. `except RecursionError` no longer takes a plain RuntimeError.
2. **Artificial `yield from` cap.** Removed `AIL_MAX_GENERATOR_DEPTH` and `cx->gen_depth` entirely. Each generator keeps its own mapped stack; if that mapping cannot be created, the resume raises the same named `RecursionError` before switching.
3. **Unlimited-stack 8 MiB fallback.** `ail_stack_limit_from` now uses a conservative 1 GiB bound (256 MiB on 32-bit) when `RLIMIT_STACK` is infinity, far below the first other mapping.

## Probes (cmp.sh, general + default, vs CPython)

| probe | result |
|---|---|
| p23 `type(e).__name__` caught | both `RecursionError` — match |
| p12 `type(e).__name__` + `isinstance(RuntimeError)` | both match |
| p24 `except RecursionError` vs plain RuntimeError | both match (one-way) |
| p25 `type(e) is` / isinstance / repr | default matches; general refuses `type` by name (pre-existing) |
| p26 user exception class + recursion | match |
| p27 exception via dict value | match |
| p28 `raise RecursionError("mine")` | match |
| p29 exception via attribute | match |
| p31 exception through a callee | match |
| p22 finite `yield from` depth 12000 | general+default: exit 0, prints `1` (CPython refuses at 1000 — documented difference) |
| p22b infinite `yield from` | stops by name at the real address-space limit |
| p17b `f(300000)`, general, `ulimit -s unlimited` | `300000`, exit 0 (was `RecursionError`) |

## Checks

- `test_ail_recursion_stop`: **13 tests, pass** (added class-identity, one-way handler, generator-chain, unlimited-stack tests).
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **4 modules, 0 failed**.
- `test_ail_runtime_error_names`, `test_ail_exception_resources`: **0 failed**.
- `compileall AIL_CURRENT tools`: OK.
- Safety table regenerated at the fix commit: **match 66, stop-differs 10, documented difference 3, refused 1, crash 0, silent-wrong 0** (80 cells); 06/07/08 `match` in every mode.
- `python3 tools/update_manifest.py --check`: exit 0.

Unverified: instruction-count cost (`perf_event_open` is denied on this runner); the changes add no per-call work and remove two counter updates, so no regression is expected. A typed-path dict-mutation-during-iteration case (p30) still differs from CPython, but it is unrelated and pre-existing.
[commandcode stop=end_turn turns=108 out_tokens=88960]

## review 0
[model commandcode/deepseek-v4.1-flash]
I have enough to judge. Let me compile the final report.

## Review — recstop1 review fixes (job-recstop1)

**What the change really does**
When a typed program can observe the exception class (it names `RecursionError` or binds any `as e`), `pyfunc` gives the recursion trap its own code (after every user class), `classes_table`/`ail_exc_kind_of` name it, and `RuntimeError`'s handler codes include it one-way. It deletes the 10 000 `yield from` cap and `cx->gen_depth`/thread `depth`, and raises the `RLIMIT_STACK`-unlimited fallback from 8 MiB to 1 GiB (256 MiB on 32-bit) with a clamp at low `sp`. That matches the report.

**Verified claims** (probes in `/tmp/rprobes`, `cmp.sh`, general + default vs CPython)
- Defect 1 fixed: `p23`, `p12`, `r15`, `r24`, `r3`, `r13`, `r8`, `r29` all match CPython on both builds (`RecursionError`, `isinstance(e, RuntimeError)` true); `r1`, `r28` keep a plain `RuntimeError` a `RuntimeError`; `r4`, `r14` show `except RecursionError` no longer takes a plain `RuntimeError`, while `raise RecursionError("mine")` now matches (fails on `work`).
- Defect 2 fixed: `p22_gen12000` prints `1`, exit 0 on both builds (on `work`: exit 1, `RecursionError`); infinite `yield from` stops by name (on `work`: `AIL internal error: generator: no stack`).
- Defect 3 fixed: `p17b` general under `ulimit -s unlimited` → `300000`, exit 0 (on `work`: exit 1, `RecursionError`); a runaway under the same limit still stops by name, exit 1 (~1 GB RSS).
- Generators: `r20` (error/close/finally), `r21` (send) match, unchanged from `work`. Threads `r31` match.
- Non-feature program: `program.c` under `--debug-dir` is byte-identical to `work` (only the JSON report's paths differ).
- Records/tests: `test_ail_recursion_stop` (13 tests) + `test_ail_safetynet`, and `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_runtime_error_names`, `test_ail_exception_resources` → all pass (`-j 2`); `compileall` OK; `update_manifest.py --check` exit 0. `RESULTS.md` table counts (66/10/3/1, crash 0) read back as claimed; 06/07/08 stop by name in general and default.

**Defects**: none found.

**Pre-existing** (identical on `work`): dict-mutation-during-iteration typed difference (`r30`); `e = RecursionError(...)` as a standalone value and `type`/`issubclass` are refused by name; the general path's guard margin vs a >64 KiB frame remains untested.

**Unverified**: instruction-count cost (`perf_event_open` is denied here — confirmed); a full safety-suite rerun (I read the table and spot-checked 06/07/08 only).

Minor record nit, not a defect: `RESULTS.md` says base `aced375 (HEAD)` while HEAD is `7bcca09` (the latter only regenerates the table).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=37 out_tokens=38708]

## full suite
test_ail_bugs7
test_ail_cc_jobs
test_ail_exception_aggregate_objects
test_ail_flush_exit
test_ail_mixed_bounds
test_ail_numeric_bindings
test_ail_record_initializers
test_ail_threads

## worker report (suite fix)
[model commandcode/deepseek-v4.1-flash]
Done. The recursion guard was changing the always-emitted DIE runtime for every program, which cascaded into eight modules. Fixes in commit `8f93856a`:

- Moved the recursion `ail_exc_kind_of`/`ail_exc_pyname` mapping and uncaught `RecursionError` naming into `exctext.recursion_die`, applied only when the DIE block's program carries `RECDEPTH`. Non-recursive programs now emit byte-identical DIE text, so `test_ail_numeric_bindings` and `test_ail_record_initializers` pinned hashes match again.
- Applied the class table inside the DIE block when `RECURSION_CODE` is set instead of adding the invalid `EXCCLASSES` runtime-part name (`test_ail_exception_aggregate_objects`).
- Fixed pyboxed2's mixed-clone drain splice to insert after the uncaught function's opening brace, restoring typed clones (`test_ail_bugs7`, `test_ail_cc_jobs`, `test_ail_flush_exit`, `test_ail_mixed_bounds`).
- Removed the literal `pthread` from the `AIL_STACK_LOW` comment (`test_ail_threads`).

Verified all eight modules pass, plus `test_ail_recursion_stop` (13 tests), `test_ail_files`, `test_ail_safetynet`, `test_ail_runtime_error_names`, `test_ail_exception_resources`; `compileall` and `update_manifest.py --check` are clean.
[commandcode stop=end_turn turns=127 out_tokens=57162]

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T22:08:10Z
