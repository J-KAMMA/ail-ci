**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
**What the change does:** replaces the legacy `_scan_borrowed_params` with an AST-level read-only-parameter analysis (`ir/borrow.py`) and uses it at the single emit point (`object_params` in `pyfunc.py`) to drop the entry retain and exit release for *every* managed reference kind (class instance, object list, bytearray, exception, file/socket), behind `AIL_RC_BORROW`; adds a verifier hook, tests, docs, and manifest entries. That is what the report describes, with one gap: the last commit (`cc86a9a "fix: uncommitted edits"`) edited `borrow.py`, `verify.py`, `pyfunc.py` and the test but did not re-run `tools/update_manifest.py`.

**Defects**

1. **Manifest is stale — the required tests and CI cannot run on the final commit.**
   - `python3 tools/update_manifest.py --check` → `stale python/pkg-v12/ir/borrow.py`, `stale python/pkg-v12/ir/verify.py`, `stale python/pkg-v12/pyfunc.py`, `stale test_ail_rc_borrow.py`.
   - `cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_rc_borrow test_ail_safetynet` → `ValueError: hash mismatch: python/pkg-v12/ir/borrow.py` (from `ail_check.preflight`). Expected: the modules run; actual: abort before any test, so every CI shard fails. Running the module directly (`python3 test_ail_rc_borrow.py`) does pass: **13 tests OK** (the report says "7/7").

2. **The number the task asked to move did not move.** The done-check requires ≥1.03x instructions on 2 programs. `lab/rc/progs/{binarytrees,cfold,deriv,linkedlist}` emit byte-identical `program.c` on HEAD and on `/tmp/base`; only `objscan` changes (6 vs 8 static `ail_obj_retain`). Achieved 1.0000x, price 0.00 — the worker admits this, but it means the sub-step's goal is unmet. `rbtree` actually emits **more** retain/release than the base (`rotate_left`/`rotate_right` gain an entry retain + exit release; 16 vs 14 static retains), which the report did not measure; I instrumented the emitted C and those functions are never called (`rotates=0`), so it costs nothing dynamically — but the "1.0000x on every program" claim is unmeasured for it.

3. **Verification shortfalls against the brief:** 40 of 200 corpus programs; valgrind not run (ASan substituted); `rbtree` and the 10 compare tasks not measured. All admitted in `RESULTS_BORROW.md`, none verified by me.

**Claims check:** borrowed-set table verified for binarytrees/objscan/linkedlist/rbtree (direct `borrow.analyze`); `objscan` −2 retains verified; `AIL_RC_BORROW=0` verified (retain counts and outputs differ); "7/7 pass" false (13 tests); "tests pass on the final commit" false (preflight aborts). Minor: `check_borrowed`'s explicit `attrs['borrow']` branch is dead (nothing anywhere sets that attribute); it only acts through the `pyfunc._BORROWED_PARAMS` path.

**Probes** (all matched CPython in the default and `AIL_UNIFIED_FORCE=1` builds, exit status included): p1 field store, p2 `list[Node].append`, p3 recursive walk with an accumulator list, w4 identity-returning list helper, w5 element stored into a holder field, w6 fill, w7 bytearray in-place mutation, w8 list/dict iteration with later mutation, y1 20k iterations of fresh `list[Node]`/`Node` temporaries passed to borrowed params (peak RSS 1316 vs base 1320 KiB — no leak), y2 object temporary stored, y3 object list stored into a field, v1 exception param + reraise, v2 bytearray aliasing, v3 list item, v4 attribute value, u1 nested-function name collision (lifted to `main__helper__0`, no elision). 11 sampled `~/corpus/gdev` programs: `program.c` byte-identical to the base (`g00_000`, `g15_002` diffed exactly; all size-identical), so unaffected code is unchanged.

**Pre-existing:** `g15_002` differs from CPython (exit 1, `Failures: 5` in its own report) identically on base and HEAD with byte-identical C.

**Unverified:** valgrind/ASan; hardware instruction counts (`perf_event_open` unavailable on this runner, as `lab/rc/run.py` records); file/socket parameters (no supported annotation found to write one); the 10 compare tasks.

VERDICT: FIX
1. Stale manifest (`python3 tools/update_manifest.py --check` reports 4 stale files; `par_check` aborts with `ValueError: hash mismatch: python/pkg-v12/ir/borrow.py`). Expected: the check passes and `par_check.py -j 2 test_ail_rc_borrow test_ail_safetynet` runs; actual: preflight error, no test runs, CI shards fail. Re-run `tools/update_manifest.py` after the final edit.
2. The task's performance target is not achieved: `lab/rc/progs/binarytrees.py`, `cfold.py`, `deriv.py`, `linkedlist.py` produce byte-identical C on HEAD and base (expected ≥1.03x instructions on 2 programs; actual 1.0000x, only `objscan` changes). Either find a case where the new rule elides something the legacy scan did not (besides `objscan`'s 2 retains/2 releases) or report the job as not meeting its price.
[commandcode stop=end_turn turns=51 out_tokens=57820]


--- ORIGINAL TASK ---
Lane: rc

# rc2: borrow inference for read-only parameters: drop their retain/release (Lean 4 style)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on rc1 merged with "go" for rc2 in `lab/rc/PRICE.md`. If it says no-go, stop and report.

**Number this moves:** run instructions (`tools/icount.c`) and peak RSS of the 6 `lab/rc/progs` programs and the 10
compare tasks, plus the dynamic retain/release count from `lab/rc/run.py`. The target is rc1's halved projection for
rc2 (at least 1.03x instructions on 2 programs), no program more than 0.3% worse in instructions, and peak RSS not
higher on any program by more than 1%.

**The rule.** A parameter of a typed function is borrowed when, on every path of the callee, it is only read: never
stored into a field, list, dict, global or closure, never returned, never rebound, never passed to a callee
position that is not itself borrowed. A borrowed parameter takes no retain on entry and no release on exit, and the
caller keeps its reference alive across the call (it already holds one). Recursion: compute a fixpoint over the call
graph, starting from "all borrowed" and demoting. Python sharing semantics are unchanged: no copy is made and no
object is freed earlier than before.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/ir/borrow.py` (new): the analysis, producing a per-function set of borrowed parameter
  indices;
- the ONE place that emits parameter retain/release, as rc1's `PRICE.md` names it. If it is `ir/emit_c.py` or
  `ir/lower.py`: a hook of at most 30 lines. If it is `pyfunc.py` (busy: codegen and pyreach lanes): a hook of at most
  15 lines in that one function, calling into `ir/borrow.py`; run `git fetch` and rebase on `origin/integ` just before
  each push;
- `AIL_CURRENT/python/pkg-v12/ir/verify.py`: an OSSA-style check that a borrowed parameter is never stored, returned
  or released (at most 40 lines);
- `lab/rc/RESULTS_BORROW.md` (new), `AIL_CURRENT/test_ail_rc_borrow.py` (new),
  `AIL_CURRENT/tests.d/test_ail_rc_borrow.txt` (new);
- the manifest files that `tools/update_manifest.py` writes.
An environment switch `AIL_RC_BORROW=0` turns the elision off, for A/B runs and as an escape hatch.

## Sub-steps

1. **Analysis and verifier (35 min).** Write `ir/borrow.py` and the verifier check, with the elision still off.
   Dump the borrowed-parameter sets for the 16 programs into `RESULTS_BORROW.md`, with 3 hand-checked examples and 3
   parameters it correctly refuses (stored, returned, passed on to an owning position). Commit, push, open the PR.
2. **Elide (25 min).** Turn it on behind the hook. Rebuild the 16 programs, the 10 compare `main.py` files and the
   first 200 sorted `lab/corpus/programs`; compare stdout and exit status with `python3` and with the
   `AIL_RC_BORROW=0` build. Run `test_ail_borrowed_owner`, `test_ail_borrowed_elements`,
   `test_ail_borrowed_element_fields`, `test_ail_callable_owned_results`, `test_ail_exception_resources`. Run 3 of the
   programs under `valgrind --leak-check=full` (smaller sizes): no new leaks, no invalid reads. Commit and push.
3. **Measure and test (20 min).** Instructions and peak RSS before/after on the 16 programs; retain/release counts.
   `test_ail_rc_borrow.py`: 4 small programs (a read-only helper, a helper that stores its argument, a recursive
   walk, a helper that returns its argument) checked against `python3` and for the expected count of
   `ail_obj_retain` in `program.c`. Register it. Fill price, achieved and achieved over price in
   `RESULTS_BORROW.md`. Commit, push, wait for CI.

## Done-check

- 0 output differences against `python3` over the 16 programs, 10 `main.py` and 200 corpus programs, in the default
  build and with `AIL_UNIFIED_FORCE=1`.
- valgrind: 0 invalid reads or writes, no new definitely-lost blocks on the 3 programs.
- Instructions: at least 1.03x on 2 programs, none worse by more than 0.3%; peak RSS none higher by more than 1%.
- The listed tests and the 20 shards pass.

## Stop rule

Stop on any wrong output against CPython or against the `AIL_RC_BORROW=0` gcc build, any valgrind invalid access, or
a use-after-free: record the program first, then turn the elision off for that case. Stop if the emit point needs
more than the hook size above. Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `optlib.py`, `ir/passes/*`, `parallel.py`,
   `typedpar.py`, `unified.py`, `stubcalls.py` or `buildcache.py`. In `pyfunc.py` touch only the one hook named above
   and never `to_c` or `_etype`. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`.
- `ail_obj_retain` is defined in the C prelude that `pyfunc.py` writes (line ~34661); class field stores retain at
  line ~35034. `ir/ownership.py` handles list sharing (move/rename); this job is about object references.
- Instruction counts: `tools/icount.c` (see rc1). Peak RSS: `/usr/bin/time -v`.
- Owner decisions: Python sharing semantics (2026-10-15); gcc `-O2`; no icount loss.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
