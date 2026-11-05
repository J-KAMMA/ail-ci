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
