Lane: stats

> Re-run of stats2, whose GitHub run was lost (no verdict 10.9 h after dispatch). If its branch job-stats2-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.

# stats2: statistics programs on the typed path (linear_regression, geometric/harmonic mean, xbar=/mu=)

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** `lab/stdlib/statistics/` programs that build on the TYPED path (no general-path note) and match
CPython: 8/12 today (01-06, 09, 12) -> 11/12 (add 07, 10, 11). 08 (NormalDist) stays refused by name.

Base: `origin/integ`. Files you may edit: `AIL_CURRENT/python/pkg-v12/statlib.py` (the typed lowering of
`statistics.*`), `AIL_CURRENT/python/pkg-v12/strt.py` (the AIL-written helpers it calls, e.g. `quantiles_int` at
about line 533), `AIL_CURRENT/test_ail_std_statistics.py`, `lab/stdlib/statistics/RESULTS.md`. Do not edit
`cruntime.py` (the general path's C) or any file in Appendix A rule 8.

How the lowering works: `statlib.py` `FUNCTIONS` (line ~30) lists the built names; `lower()` (line ~235) dispatches by
name, refuses keywords except for `fmean`, and calls `self.call('<helper>', ...)`, which calls a function of `strt.py`.
Read `lower_quantiles` and `lower_pair` first and copy their shape.

## Sub-steps

1. **Baseline (10 min).** Build all 12 programs with the default command (`--syntax python`, in a temp dir). Record
   typed / general / refused and the first stderr line per program in a new "Before (integ <short sha>)" table at the top of
   `RESULTS.md`. Commit, push, open the PR against `integ`.
2. **xbar= and mu= (15 min).** `variance(xs, xbar=v)`, `stdev(xs, xbar=v)`, `pvariance(xs, mu=v)`, `pstdev(xs, mu=v)`
   for `list[int]` with an int keyword value. Copy CPython 3.12's algorithm exactly: read it with
   `python3 -c "import inspect,statistics;print(inspect.getsource(statistics.variance))"` (and `_ss`, `pvariance`).
   The result must be the same float CPython prints. Use the same exact-sum method the existing int `variance` helper
   in `strt.py` uses; if that helper cannot take a given centre exactly, refuse the keyword form by name (the general
   path then still builds the program, as today). Program 10 must become typed. Commit.
3. **geometric_mean and harmonic_mean of list[int] (20 min).** Read CPython's source the same way. `geometric_mean`
   is `exp(fmean(map(log, data)))` and raises `StatisticsError` for empty or non-positive data; `harmonic_mean` is
   exact (`n / sum of 1/x` as fractions, then one rounding). Build them only where the result is the same bits as
   CPython's for every int64 input. An int64 numerator/denominator that can overflow is not enough: an overflow
   would stop a program that the general path runs correctly today (a regression). So either the helper is exact for
   every int64 input, or the typed lowering refuses that form by name and the general path keeps building it. Error texts must be CPython's. Program 11 must become typed. Commit.
4. **linear_regression (20 min).** `statistics.linear_regression(x, y)` and `proportional=True` over `list[int]`,
   CPython 3.12's float algorithm (read the source; it uses `fsum`/`sumprod`-style sums: reproduce the same rounding).
   The result object prints as `LinearRegression(slope=2.0, intercept=1.0)` and has `.slope` and `.intercept`. Use a
   small class defined in the `strt.py` helpers (fields `slope: float`, `intercept: float`, a `__repr__`), the way
   `hashlower.py` uses the class `_AilHash`. Errors: `StatisticsError` texts as CPython ("linear regression requires
   that both inputs have same number of data points", "... at least two data points", "x is constant"). Program 07 must
   become typed. Commit.
5. **Test and results (10 min).** In `test_ail_std_statistics.py` move 07 to `PASSING`, and add an assertion that 07,
   10 and 11 build with no `built on the general path` note. Add probes as extra cases in the test: an empty list, a
   one-element list, negative values, values near 2**62 (CPython gives a float; AIL must not stop). Update `RESULTS.md`
   with an "After" table. Run `python3 tools/par_check.py -j 2 test_ail_std_statistics test_ail_stdlib_reach`. Push.

## Done-check

11/12 programs typed and equal to CPython; 08 still refused by name; the test asserts the typed builds; 20 shards pass.

## Stop rule

If a function cannot be made bit-identical to CPython in 20 minutes, leave it refused by name (as today), record why in
`RESULTS.md`, and go on to the next sub-step. Stop when 80 minutes pass; push what is done and report the number reached.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. Turning a
   correct program into a refusal or a stop is a regression. When a new fast path cannot handle a case, keep the old route.
2. Probe ints beyond int64 wherever ints come from text, fields or arithmetic. Run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, and compare both with `python3`.
3. Push early and open the PR against `integ`. Wait for all 20 `shard` checks on your head commit
   (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `origin/integ` (or from one unmerged PR at most; never from a PR that is itself stacked).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: add `AIL_CURRENT/tests.d/<module>.txt` (one line: the module name), `git add` every new file, run
   `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, tag, publish, change repository settings, cancel runs, or edit
   `.github/workflows`.
8. Files owned by busy lanes; do NOT edit them: `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`,
   `AIL_CURRENT/python/pkg-v12/pyfunc.py`, `pyc.py`, `buildcache.py`, `pyboxed2.py`, `packaging/ail_lang/cli.py`.
   Also do not edit `DEVLOG.md` or `AIL_CURRENT/DEVLOG.md` (integration writes them). If a fix needs one of these files,
   do not make it: write a finding (file, function, what is needed, the refusal text) in your results file and go on.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC.py -o OUT [--syntax python] [--strict] [--exact-int]
  [--debug-dir DIR]`. `-o` must not exist yet. The default build tries the typed path first; when it falls back it prints
  `note: ... built on the general path` on stderr. No such note = typed. `--strict` = typed path or refuse.
  `DIR/program.c` is the generated C. Use `AIL_NO_CACHE=1` for timings.
- One test module: `python3 tools/par_check.py -j 2 test_ail_<name>`.
- Model test file: `AIL_CURRENT/test_ail_std_statistics.py` (build each program in a temp dir, run it, compare stdout and
  exit code with `python3 <program>`).
- Instruction counts: `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
  `/tmp/icount PROG ARGS < input`. If `perf_event_open` is refused, run `sudo sysctl -w kernel.perf_event_paranoid=1`
  once; if it is still refused, use the median of 5 wall times and say so in the results.
- The oracle is CPython 3.12 (`python3`). Peak RSS: `/usr/bin/time -v PROG` ("Maximum resident set size").
- AIL is Python syntax plus optional annotations. Ints are int64 by default and overflow stops loudly;
  `--exact-int` gives exact ints.

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
