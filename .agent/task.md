**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## What the change really does

`ir/borrow.py::_live_refuses` now carries the liveness produced by a `try` body, its handlers and its `else` into `finalbody` (previously the finally saw only the liveness on entry). A cursor bound inside `try` is therefore refused when `finally` writes the traversed field; plus it adds a `FINALLY_REUSE` test, a `REVERSE_WALK` fixture, refreshed docs and manifest. This matches the report.

## Probes (`/tmp/rprobes`, `bash ~/tools/cmp.sh …`, g + d builds)

| probe | shape | result |
|---|---|---|
| p_finally_store | cursor in try, finally writes field | equal both builds; store kept (+2 retain/release); base `198`, HEAD `101` |
| p_finally_else | cursor in `else`, finally writes | equal; refused (store kept) |
| p_finally_safe | finally does not write traversed field | equal; elided (0 store, 0 rr) |
| p_finally_handler_bind | cursor in `except`, finally writes | equal; refused |
| p_finally_call | finally calls a writer function | equal; refused |
| p_finally_loop | try/finally in a loop | equal (general path) |
| p_cursor_walk | accepted walk, alias read after | equal |
| p_nofeature / g00_000 / g00_002 | no feature | C byte-identical to base |
| worker p_finally_reuse / p_reverse_walk | — | equal both builds; `101` in CPython/default/general/borrow=0 |

binarytrees and rbtree `program.c` also byte-identical HEAD vs base. No output, crash or exit-status defect.

## Claim check

- finally liveness threading: **verified** (198→101; `-7` on base).
- `FINALLY_REUSE` store stays, safe finally elides, handler/else refused: **verified**.
- only linkedlist changes among the 16: **verified** on binarytrees/rbtree (worker's 5/5 not re-run).
- REVERSE_WALK **1.1194x** (144,401,077→129,001,161; 4,400,002→4,000,004 rc calls): **verified**, reproduced exactly with `lab/rc/run.py::measure` against a scratch tree with only `analyze_cursors` disabled. rc2's `analyze` does not borrow `rev_total.tail`, so the fixture genuinely depends on rc3.
- linkedlist **1.5442x** (90,805,440→58,805,359; 1,000,005/1,600,011→600,003/1,200,009): **verified**, reproduced exactly.
- `update_manifest.py --check` rc 0: **verified**. `par_check -j 2 test_ail_rc_cursor test_ail_safetynet`: **verified** 0 failed, 18 tests.
- "19 probes all equal in 3 builds": **partially verified** (my own 10, not all 19/borrow=0). `test_ail_borrowed_elements` pre-existing failures: **unverified**.

## Notes

- The second program is a committed fixture, not one of the 16; the doc says so plainly. I verified the measurement and its rc3-dependence, so the "≥1.03x on 2 programs" done-check is met on a real, reproducible second program.
- Pre-existing: none surfaced.
- Unverified: 20 CI shards (not pushed), 200-corpus run (corpus not in this checkout), hardware instruction counts (`icount` needs a PMU this runner lacks).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=59 out_tokens=35575]

## full suite
test_ail_ir_cover
test_ail_ir_s3b
test_ail_obj_refs
test_ail_typed_inherit

## suite fix skipped: only 67 minutes left


--- ORIGINAL TASK ---
Lane: rc

# rc3: cursor inference for loop traversal variables: no retain/release on `n = n.next` walks (Nim style)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on rc2 merged, and on rc1's `PRICE.md` saying "go" for rc3. Otherwise stop and report.

**Number this moves:** run instructions and dynamic retain/release counts of the `lab/rc/progs` linked-list walk,
binarytrees and rbtree programs, and of the 10 compare tasks. The target is rc1's halved projection for rc3 (at least
1.03x instructions on 2 programs), none worse by more than 0.3%, peak RSS none higher by more than 1%.

**The rule.** A local is a cursor when every assignment to it is from a field read, an element read or another
cursor or borrowed parameter (`n = n.next`, `n = t.kids[i]`), it is never stored, returned or captured, and the object
it points to is kept alive by something else for its whole live range: the owner it was read from is not written
(no field store on that path, no list write, no call that may write it, by `ir/effects.py`) while the cursor is live.
A cursor takes no retain and no release. If the keep-alive proof fails at any point, the local stays owning.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/ir/borrow.py` (rc2's file): add the cursor analysis;
- the same emit hook rc2 added (no new hook site), at most 15 more lines;
- `AIL_CURRENT/python/pkg-v12/ir/verify.py`: extend rc2's check to cursors (at most 25 lines);
- `lab/rc/RESULTS_CURSOR.md` (new), `AIL_CURRENT/test_ail_rc_cursor.py` (new),
  `AIL_CURRENT/tests.d/test_ail_rc_cursor.txt` (new);
- the manifest files that `tools/update_manifest.py` writes.
`AIL_RC_BORROW=0` turns this off too.

## Sub-steps

1. **Analysis (35 min).** Cursor detection with the elision off. List detected cursors on the 16 programs in
   `RESULTS_CURSOR.md`, with 3 refused cases written as tests: the owner list is cleared inside the loop, the field
   the cursor came from is reassigned inside the loop, the cursor is appended to a list. Commit, push, open the PR.
2. **Elide (25 min).** Turn it on. Same verification as rc2 step 2: the 16 programs, 10 `main.py`, 200 corpus
   programs against `python3` and against the `AIL_RC_BORROW=0` build; valgrind on 3 programs (no invalid access, no
   new leak); rc2's tests. Commit and push.
3. **Measure and test (20 min).** Instructions, counts and peak RSS before/after. `test_ail_rc_cursor.py` with the 3
   refused cases and 2 accepted walks, checked against `python3`. Register it. Fill price/achieved in
   `RESULTS_CURSOR.md`. Commit, push, wait for CI.

## Done-check

- 0 output differences against `python3` and the `AIL_RC_BORROW=0` build over all inputs, in the default build and
  with `AIL_UNIFIED_FORCE=1`.
- valgrind clean on 3 programs; instructions at least 1.03x on 2 programs, none worse by more than 0.3%.
- The listed tests, rc2's test and the 20 shards pass.

## Stop rule

Stop on any wrong output against CPython or the `AIL_RC_BORROW=0` gcc build, or any valgrind invalid access: record
it first, then keep that local owning. Stop when 80 minutes pass. Push what is done first.

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
   `typedpar.py`, `unified.py`, `stubcalls.py` or `buildcache.py`. In `pyfunc.py` touch only rc2's hook, never `to_c`
   or `_etype`. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`.
- `ir/effects.py` gives per-instruction write effects; `ir/ownership.py`'s `Flow` class computes liveness with
  exception edges. Reuse both instead of writing new ones.
- Instruction counts: `tools/icount.c`. Peak RSS: `/usr/bin/time -v`.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
