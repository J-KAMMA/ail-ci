Lane: hybrid

**Finish cpyhyb2 from its existing work; do not redo it.** The first run (branch `job-cpyhyb2-11031804`) ran out of
model quota. Its only work is the commit "worker: uncommitted edits" (`66200052`), and it got no review verdict.

Start on a branch from `origin/integ`:

```
git fetch origin job-cpyhyb2-11031804
git cherry-pick 66200052
git checkout origin/integ -- AIL_CURRENT/ail_chatgpt.py
git commit -m "hybrid: keep ail_chatgpt.py as on integ"
```

The `git checkout` line drops that commit's `--hybrid` rename in `ail_chatgpt.py`: other lanes edit that file. In this
job, do NOT edit `AIL_CURRENT/ail_chatgpt.py`, `packaging/`, or anything under `AIL_CURRENT/python/pkg-v12/`. The flag
`ail build --cpython SOURCE -o DIR` stays exactly as it is on integ.

**Owner decision (2026-11-01):** the standalone binary stays the default. The hybrid is an extra: functions that compile
on the typed path become a CPython extension module, and the rest of the program runs on CPython unchanged.

# cpyhyb2b: the hybrid build, checked against CPython on 40 programs

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** of 40 programs (the 10 compare-lab tasks and 30 corpus programs), how many give the same stdout,
exit status and last stderr line as CPython when run as a hybrid (today: never measured). Also reported: functions
that went native per program, and hybrid wall time against CPython on the 10 tasks.

Base: `origin/integ`.

## Sub-steps

1. **Apply and repair (15 min).** Apply as above. Read the diff of `AIL_CURRENT/ail_cpython_hybrid.py`: `build()`
   (about line 981) now writes `<stem>_run.py` and the schema `ail.cpython_hybrid/2`. Read
   `AIL_CURRENT/test_ail_cpython_hybrid.py`. Since the CLI rename is dropped, no test may use `--hybrid`: use
   `ail_chatgpt.py build --cpython SOURCE -o DIR` or call `ail_cpython_hybrid.build(src, out)` directly.
   Add a standalone entry at the end of `ail_cpython_hybrid.py`, inside `if __name__ == "__main__":`:
   `python3 AIL_CURRENT/ail_cpython_hybrid.py SOURCE [-o DIR]`. The default DIR is
   `SOURCE.parent / (SOURCE.stem + "_hybrid")`. It prints `built DIR: N function(s) accelerated` and
   `run DIR/<stem>_run.py`. Run `test_ail_cpython_hybrid`. Commit, push, open the PR.
2. **Correctness script (25 min).** Write `lab/hybrid/check.py`. The programs are:
   - the 10 `lab/compare/src/<task>/main.py`, fed exactly the input compare-lab feeds them (read
     `lab/compare/run_task.py` to see how each task gets its input or arguments);
   - the first 30 files, sorted by path, matching `lab/corpus/programs/*/t*.py`. Give them stdin from `/dev/null`.

   For each program, build the hybrid into a fresh temp dir. Then run `python3 DIR/<stem>_run.py` and
   `python3 SOURCE` with the same stdin and arguments. Compare stdout, exit status and the last stderr line. Use a
   60-second timeout per run.
   Write `lab/hybrid/RESULTS.md` with one row per program: program | native functions | Python functions | match.
   For each mismatch, give the first differing line. Commit, push.
3. **Fix mismatches (20 min),** only in `ail_cpython_hybrid.py`: function selection in `_select` (about line 534), the
   wrapper in `_wrapper_source` (about line 606). If a fix needs the compiler, do not fix it. Instead, keep that
   function in Python (do not accelerate it) and list it in RESULTS.md with the reason. Re-run `check.py`. Commit, push.
4. **Numbers (15 min).** On the 10 tasks, measure wall time (median of 5) for `python3 main.py`, the hybrid, and the
   standalone binary from `ail_chatgpt.py compile`. Measure instruction counts with `tools/icount.c` if the runner
   allows it; otherwise write "unavailable" and the error. Add these to RESULTS.md.
   Then byte-compare `--debug-dir DIR/program.c` of the standalone build on all 10 tasks, HEAD against `origin/integ`
   (`git worktree add /tmp/base origin/integ`). All 10 must be identical. Commit, push.

## Done-check

- `test_ail_cpython_hybrid` and `test_ail_safetynet` pass.
- RESULTS.md has 40 rows. Every mismatch is fixed, or its function is kept in Python and explained.
- 10/10 `program.c` files are identical to integ.
- All 20 shards pass.

## Stop rule

Stop if any of these happens. Then push what is green and report.

- A mismatch needs a change outside `ail_cpython_hybrid.py`, its test, and `lab/hybrid/`.
- The extension cannot be built on the runner (for example, no `Python.h`). Record the exact error.
- The standalone `program.c` changes.
- 80 minutes pass.

## Appendix A: standing rules

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `--check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, or edit
   `.github/workflows`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--debug-dir DIR]`. `DIR/program.c` is the
  generated C. `-o` must not exist yet.
- `ail_chatgpt.py build --cpython SOURCE -o DIR` (argparse about line 6179, handler about line 6619) calls
  `ail_cpython_hybrid.build(Path(source), Path(out))` and prints the report.
- Design: `docs/design/CPYTHON_HYBRID.md`, sections 1 (unit of acceleration) to 6 (what stays standalone).
- compare-lab tasks: berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank
  ticket_audit tree_fold. `EXACT_INT_TASKS = ('rail_transfer', 'chain_relax')` build with `--exact-int`.
- `lab/corpus/programs/<model>/tNNN.py` holds 221 generated programs; `status.jsonl` sits beside them.
- Probes: `bash ~/tools/cmp.sh PROBE.py $PWD` builds the general path and the default path, then diffs both against
  CPython.

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
