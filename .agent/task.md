**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1 skipped: only 10 minutes left


--- ORIGINAL TASK ---
Lane: hybdoc

# hybex1: six CPython-hybrid examples (`ail build --cpython`), checked against CPython, with measured speed-ups

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** user-facing examples of the CPython hybrid. In a hybrid build, typed functions run as a C
extension and the rest runs in CPython. Each example must print exactly what `python3` prints, with the same exit
status, and a test must check it. This goes from 0 examples today (there is no `examples/hybrid/`) to 6, plus a
table of `python3` wall time against hybrid wall time (median of 3). Target: at least 4 of the 6 have a function
that is actually accelerated, and at least 3 run ≥ 2× faster than `python3`. This is roadmap P4, the hybrid docs
and examples.

Base: `origin/integ`. Files you may create or edit, and no others:
- `examples/hybrid/` (new): the programs, input generators and `README.md`
- `AIL_CURRENT/test_ail_examples_hybrid.py` and `AIL_CURRENT/tests.d/test_ail_examples_hybrid.txt` (new)
- the manifest files that `tools/update_manifest.py` writes

Do not edit `AIL_CURRENT/ail_cpython_hybrid.py`, `AIL_CURRENT/test_ail_cpython_hybrid.py` or
`docs/design/CPYTHON_HYBRID.md`. The hybrid lane owns them. Write every limit you hit in `examples/hybrid/README.md`
as a finding, with the smallest program that shows it.

Read first: `docs/design/CPYTHON_HYBRID.md` sections 1-2. They give which functions are candidates: top-level, with
parameters annotated `int`, `bool`, `float`, `str`, `list[int]` or `list[float]`, and none of the body operations
the prototype refuses. Also read `AIL_CURRENT/test_ail_cpython_hybrid.py`. It shows the exact build command
(`ail_chatgpt.py build --cpython SRC -o OUT`), how the result is run, and how the test sees which functions were
accelerated. Use the same method.

## Sub-steps

1. **First example and the method (20 min).** Write `examples/hybrid/collatz.py`, a whole program. Its `main()`
   reads `N` from `sys.argv` (default 300000), does its I/O and formatting in plain Python, and calls one hot
   function: `def longest(limit: int) -> int` loops over the Collatz steps for every start below `limit`. Choose the
   body so that the hybrid accepts it under the rules you read. Build it with `--cpython` and run it. Check that the
   function was accelerated, and compare the output with `python3`. Time both, median of 3. Commit, push, and open
   the PR against `integ`.
2. **Five more (25 min).** One hot function each, written as a user would, within the candidate rules:
   - `mandel_rows.py`: float iterations of the Mandelbrot set, with ASCII output from Python;
   - `prime_count.py`: a count by trial division, if the rules allow `%`; if they do not, use some other
     integer-only loop and record the `%` limit;
   - `checksum_text.py`: a `str` parameter and a rolling hash loop over `ord` of its characters, if the rules allow
     it;
   - `sum_squares_list.py`: a `list[float]` parameter iterated with `for x in xs`;
   - `fallback_demo.py`: the same function called with a type that is not its annotated one, to show the call going
     back to CPython. Its output must still match.
   For every example, record whether the function was accelerated, and if not, the rule that refused it. Commit
   and push.
3. **Test (15 min).** Write `AIL_CURRENT/test_ail_examples_hybrid.py`. It builds every example with `--cpython`,
   runs it with a small argument, and requires stdout and the exit status to equal `python3`'s. For each example
   the README marks as accelerated, it asserts that the function really was accelerated. It skips when `Python.h`
   or a C compiler is missing. Register the test and run it. Probe an int above int64 in `collatz.py` (a start of
   `2**63 + 1` given in `argv`): the output must still match CPython, through the fallback. Commit and push.
4. **README (15 min).** Write `examples/hybrid/README.md`. It explains what the hybrid is, in 5 lines, and the build
   and run commands for a checkout and for the installed `ail`. It lists the rules a function must follow to be
   accelerated, each with a one-line example. Then the table: example, accelerated (yes/no), `python3` ms, hybrid
   ms, speed-up. Then the findings. Every number comes from a run in this job. Commit, push, and wait for CI.

## Done-check

- 6 examples match CPython in the test.
- At least 4 are accelerated, or the README names the rule that blocks each one that is not.
- The table is filled.
- The 20 shards pass.

## Stop rule

Stop and report if `build --cpython` does not work on the runner (no `Python.h`, or a build error); give the exact
text. Also stop if fewer than 2 examples can be accelerated under the current rules: write the blocking rules as
findings. Stop when 80 minutes pass. Push what is done first.

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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.

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
