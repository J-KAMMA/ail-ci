Lane: selfhost

**Finish selfhost1 from its existing work; do not redo it.** The run on branch `job-selfhost1-11040509` did the work, then ended ERROR because the pipeline's review step crashed (a bug in the job runner, now fixed; not your work's fault), so it got no verdict.

Start by checking whether `origin/integ` already contains this work: if `git diff origin/integ...origin/job-selfhost1-11040509` adds nothing new, report NOCHANGE and stop.

Otherwise apply that branch's work: cherry-pick, in order, every commit after "export of staging:integ + task" except "agent worker report".

```
git fetch origin job-selfhost1-11040509
git log --oneline origin/job-selfhost1-11040509
```

Commits named "worker: uncommitted edits" or "fix: uncommitted edits" hold unfinished work: read them, then finish the job.

Then verify against the original task below: re-run its measurements and targeted tests, check the boundary cases, fix what is wrong, and report the numbers. Time budget: 60 minutes.

**Self-hosting, step 1: a census of the compiler's own functions. Measure only.** The owner likes rewriting compiler
parts in AIL (2026-10-31): census first, the hot part first, then a byte-identical C diff as the check. This job is
the census. It tells us which compiler functions AIL can already compile on the typed path, which are hot, and why the
rest fall off.

# selfhost1: census of the compiler's functions on the typed path

Time budget: 75 minutes. Commit and push after each sub-step.

**Number this moves:** two numbers, measured for the first time:
- the share of the compiler's top-level functions that AIL accepts on the typed path;
- the same share among the 30 hottest compiler functions of a real build.

Base: `origin/integ`.

## Scope

- Files to read (and never edit):
  - `AIL_CURRENT/python/pkg-v12/*.py`
  - `AIL_CURRENT/ail_chatgpt.py`
  - `AIL_CURRENT/ail_syntax.py`
  - `AIL_CURRENT/ail_modules.py`
- Files to write:
  - `tools/selfhost_census.py`
  - `lab/selfhost/census.json`
  - `lab/selfhost/CENSUS.md`
  - `DEVLOG.md`
- The unit is a top-level function (`def` at module level), the same unit as the CPython hybrid. Methods are counted
  separately as "in a class", with no per-method verdict.

## Sub-steps

1. **Classifier (20 min).** Write `tools/selfhost_census.py FILE...`. For each file, it takes each top-level function
   and decides accept or reject using the CPython hybrid's selection: `ail_cpython_hybrid._analysis` (line 365) and
   `_select` (line 534) in `AIL_CURRENT/ail_cpython_hybrid.py`. Read them first.
   - Call them without building an extension. If that is impossible, call `ail_cpython_hybrid.build(src, tmpdir)`
     and read `report['accelerated']` and `report['rejected']` (a dict of function name to reason).
   - Record for each function: file, name, line, length in lines, verdict, and the first reason.

   Try it on `python/pkg-v12/fastwalk.py` (49 lines) and `fecache.py`. Commit, push, open the PR.
2. **Run (20 min).** Run the classifier on every file in scope, one file per process, under `ulimit -v 1500000` with a
   300-second timeout per file. `pyfunc.py` is 41,000 lines. If it does not finish, split it: classify its functions
   in chunks by line range, and say so. Write `lab/selfhost/census.json`. Commit, push.
3. **Hot functions (15 min).** Profile 3 cold builds with `python3 -m cProfile`:
   `lab/compare/src/{chain_relax,tree_fold,tally_lang}/typed.py`. Use a fresh `AIL_CACHE` and `TMPDIR`, and
   `AIL_SERVER=0`. The child `pyc.py` process does most of the work, so profile it too: print its command line once
   from a scratch copy, as described at `ail_chatgpt.py` about line 6556, but do not commit that.
   Take the 30 compiler functions with the most `tottime` summed over the 3 builds. Join them with the census.
   Commit, push.
4. **Report (15 min).** Write `lab/selfhost/CENSUS.md`:
   - totals: functions, accepted, rejected, and in a class;
   - the share accepted overall and per file (the 15 largest files);
   - the top 10 rejection reasons with counts;
   - the 30 hot functions, each with its verdict and reason;
   - one paragraph naming the 3 hot functions that are closest to accepted, as candidates for the first rewrite
     step.

   Commit, push.

## Done-check

- `census.json` covers every file in scope, or names each file it skipped and why.
- CENSUS.md has both numbers.
- `git diff origin/integ --stat` touches only `tools/selfhost_census.py`, `lab/selfhost/` and `DEVLOG.md`.
- `tools/update_manifest.py --check` passes.
- All 20 shards pass.

## Stop rule

Stop if any of these happens. Then push what is green and report.

- The selection functions cannot be used without editing `ail_cpython_hybrid.py`. Report what blocks them; do not
  edit that file, because the hybrid lane owns it.
- A single file needs more than 1.5 GB.
- 75 minutes pass.

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

- The compiler is about 180,000 lines of Python. `python/pkg-v12/pyfunc.py` is the typed-path code generator
  (41,059 lines), and `pyc.py` is the child-process driver.
- `ail_cpython_hybrid.py`: the report holds `accelerated` (a list of names) and `rejected` (name to reason). The
  design is in `docs/design/CPYTHON_HYBRID.md`, section 1 (the unit of acceleration).
- Cold build: `AIL_CACHE=$(mktemp -d) TMPDIR=$AIL_CACHE AIL_SERVER=0 python3 AIL_CURRENT/ail_chatgpt.py compile
  SRC -o OUT`.
- Measured 2026-11-04: a chain_relax build is 3.69 CPU s, of which Python is 3.05 s and the child `pyc.py` is about
  3.0 s.

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
