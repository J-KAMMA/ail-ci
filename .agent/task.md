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
