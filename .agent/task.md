Lane: reldocs

**Finish relnotesc from its existing work; do not redo it.** The run on branch `job-relnotesc-11040507` did the work, then ended ERROR because the pipeline's review step crashed (a bug in the job runner, now fixed; not your work's fault), so it got no verdict.

Start by checking whether `origin/integ` already contains this work: if `git diff origin/integ...origin/job-relnotesc-11040507` adds nothing new, report NOCHANGE and stop.

Otherwise apply that branch's work: cherry-pick, in order, every commit after "export of staging:integ + task" except "agent worker report".

```
git fetch origin job-relnotesc-11040507
git log --oneline origin/job-relnotesc-11040507
```

Commits named "worker: uncommitted edits" or "fix: uncommitted edits" hold unfinished work: read them, then finish the job.

Then verify against the original task below: re-run its measurements and targeted tests, check the boundary cases, fix what is wrong, and report the numbers. Time budget: 60 minutes.

he existing work of relnotesb; do not redo it.** The run on branch `job-relnotesb-11032053`
finished the work, then its review hit a model usage limit, so it got no verdict.

Start on a branch from `origin/integ`:

```
git fetch origin job-relnotesb-11032053
git cherry-pick 907eaa19 546e61f4 a4188d89 6ae60041
```

Resolve any `DEVLOG.md` conflict by keeping both entries. Then do the verification the review never did.

# relnotesc: README, CHANGELOG and install guide, every claim checked

Time budget: 70 minutes. Commit and push after each sub-step.

**Number this moves:** the share of behaviour claims in `README.md`, `CHANGELOG.md` and `docs/INSTALL.md` that hold on
current integ, from unchecked to 100%. Every fenced `python` block in README.md runs and matches CPython
(`test_ail_readme`).

Base: `origin/integ`.

**Facts as of 2026-11-04 (integ 095e0321).**
- Merged: relevalorder, reldiag, relpkgname, relplatinstall, reltable, relwheelfix.
- NOT merged: relrterr ("runtime errors name the exception and the source line in the default build"); it is still
  in progress. clihelp is not merged either.

So a sentence that says runtime errors show the exception name and line in the default build must be reworded to
what integ does today, or moved under "Known limitations". The same goes for anything that describes the new
`ail --help` layout.

## Sub-steps

1. **Apply (10 min).** Apply as above, then run `test_ail_readme` and `test_compare_publish`. Commit, push, open the
   PR.
2. **Claim audit (30 min).** List every sentence in the three files that states a behaviour: a command, a flag, an
   error text, an exit status, int64 overflow, `--exact-int`, the PyPI name `ailc`, the command `ail`, the licence,
   or a supported or unsupported feature. For each one, run a command on HEAD that shows it, for example:
   - `python3 -B AIL_CURRENT/ail_chatgpt.py compile x.py -o x && ./x; echo $?`
   - `python3 -m ail_lang.cli ...` with `PYTHONPATH=$PWD/packaging AIL_SDK_DIR=$PWD/AIL_CURRENT`

   Put the table in the PR body, not in a file: claim | command | result | holds?
   Fix or remove every claim that does not hold.
   Every number in README.md must appear in `docs/COMPARISON.md` or in the scorecard lines `test_compare_publish`
   checks. Otherwise, replace the number with a link. Commit, push.
3. **Install guide (15 min).** Check `docs/INSTALL.md` against:
   - `packaging/pyproject.toml` (if present) or `packaging/ail_wheel_backend.py`, for the distribution name and the
     console script;
   - `tools/wheel_check.py`, for what CI tests on Linux, macOS and Windows.

   State the C compiler needed on each OS exactly as `wheel_check.py` or the relplatinstall CI job assumes it.
   Commit, push.
4. **Final run (10 min).** Run `test_ail_readme`, `test_compare_publish`, `test_ail_safetynet` and
   `tools/update_manifest.py --check`. Commit, push.

## Done-check

- The audit table in the PR body has every claim marked as holding.
- The four tests pass.
- `git diff origin/integ --stat` touches only `README.md`, `CHANGELOG.md`, `docs/INSTALL.md`, `DEVLOG.md`,
  `AIL_CURRENT/test_ail_readme.py`, its `tests.d` entry and manifest files.
- All 20 shards pass.

## Stop rule

Stop if any of these happens. Then push what is green and report.

- Making a claim true would need a code change. Reword the claim instead; never change code here.
- A version number, tag or publish step would be needed. The owner does those.
- 70 minutes pass.

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

- The owner's facts to state:
  - AIL is Python syntax with optional annotations, compiled to a small native binary.
  - int64 is the default, and overflow stops the program loudly; `--exact-int` gives big integers.
  - The PyPI package is `ailc` and the command is `ail`.
  - The licence is MIT OR Apache-2.0.
- `AIL_CURRENT/test_ail_readme.py` (from relnotesb) extracts the fenced `python` blocks of README.md, runs them with
  `ail run`, and compares the output with CPython.
- `tools/compare_publish.py` writes the compare-lab scorecard; `AIL_CURRENT/test_compare_publish.py` checks the
  README lines it owns.

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
