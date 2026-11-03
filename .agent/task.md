Lane: fuzzpy

**Finish fuzzpy from its existing work; do not redo it.** The first run (branch `job-fuzzpy-11031805`) wrote the
generator and runner, then ran out of model quota. Its work is the commit "worker: uncommitted edits" (`304e86a8`),
and it got no verdict.

Start on a branch from `origin/integ`:

```
git fetch origin job-fuzzpy-11031805
git cherry-pick 304e86a8
git rm -r -q --cached lab/fuzzpy/out
printf 'out/\n' > lab/fuzzpy/.gitignore
git add lab/fuzzpy/.gitignore
git commit -m "fuzzpy: keep run output out of git"
```

Keep `lab/fuzzpy/gen.py` and `lab/fuzzpy/run.py`. The three raw findings in `lab/fuzzpy/out/findings/` (`seed9-DIFF`,
`seed45-DIFF`, `seed22-crash`) stay on disk as input for step 3.

# fuzzpyb: differential fuzzing of plain Python on the default build (find and file, no compiler edits)

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** the number of generated programs compared against CPython goes from 0 to 500. Each distinct
cause of a difference is filed as a reduced program, with silent wrong outputs listed first.

Base: `origin/integ`.

## Sub-steps

1. **Smoke (15 min).** Apply as above. Read `gen.py` and `run.py`. Run 20 seeds and check that the comparison works:
   stdout, the last line of stderr, and the exit status, under `ulimit -v 1500000` with a 10-second timeout each.
   Fix the scripts only. Commit, push, open the PR.
2. **Run 500 programs (25 min).** Use seeds 1-500, 2 at a time, in chunks of 100. After each chunk, commit
   `lab/fuzzpy/summary.json`: seed | class | typed-path or general | first differing line. Use these classes:
   - `silent`: different stdout and exit 0 on both;
   - `loud-ok`: AIL stops on int64 overflow and CPython goes on. This is correct by owner decision; count it, but do
     not file it;
   - `crash`: signal or segfault;
   - `refused`: a named compile-time refusal;
   - `other`.
3. **Reduce and file (25 min).** Start with the three raw findings, then take each distinct cause in `silent`,
   `crash` and `other`. Reduce each one by hand to the smallest program that still differs. Save it as
   `lab/fuzzpy/findings/NNN.py`, with comment lines at the top giving the CPython output, the AIL output, and a
   one-line guess at the cause. Confirm each one with `bash ~/tools/cmp.sh lab/fuzzpy/findings/NNN.py $PWD`.
   Commit, push.
4. **Report (10 min).** Write `lab/fuzzpy/REPORT.md` with: the number of programs run, the typed-path share, the
   count per class, and the findings list with silent wrong outputs first. Commit, push.

## Done-check

- `summary.json` has 500 rows.
- Every file in `findings/` reproduces with `cmp.sh`.
- REPORT.md counts add up to 500.
- `git diff origin/integ --stat` touches only `lab/fuzzpy/` and `DEVLOG.md`.
- All 20 shards pass.

## Stop rule

Stop if any of these happens. Then push what is green and report.

- You are about to edit a compiler file. This job only finds and files.
- The run rate is under 100 programs per 10 minutes. Stop at the seeds done, and say so.
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

- Run a program: `python3 -B AIL_CURRENT/ail_chatgpt.py run PROG.py` (default build). `AIL_UNIFIED_FORCE=1` forces
  the general path.
- `bash ~/tools/cmp.sh PROG.py $PWD` builds both paths and diffs each against CPython 3.12.
- Owner decisions:
  - int64 is the default, and overflow stops loudly (`OverflowError`, exit 1). That is not a bug.
  - The recursion limit is 50,000 frames, while CPython's is about 1,000. A difference that comes only from the
    limit is not a bug.
- Existing differential tooling to borrow from: `lab/fuzz/` (the older brace-source fuzzer) and the daily `fz*`
  jobs.

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
