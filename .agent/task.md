Lane: pkg

# pkgcheck1: the installed `ailc` wheel builds the same C as the checkout, and its size is known

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** programs that build from an INSTALLED wheel with a `program.c` byte-identical to the checkout
build: not measured today -> N / (10 compare-lab `main.py` + 18 lab/stdlib programs). A file the wheel forgets (a
`.h`, a `stdlib/*.py`, a pinned `.c`) shows up here before users see it. Second number: wheel bytes and installed bytes,
with the 20 biggest files, and any file shown to be unused at run time removed from the wheel.

Base: `origin/integ`. Files you may edit: `tools/wheel_check.py`, `packaging/ail_wheel_backend.py`,
`AIL_CURRENT/test_ail_packaging.py`, new `packaging/WHEEL_REPORT.md`. Read only: `lab/compare/`, `lab/stdlib/`,
`AIL_CURRENT/ail_sdk.py` (`export_sdk`, line ~715, chooses the SDK files). Do not edit `packaging/ail_lang/cli.py` or any
file in Appendix A rule 8. Do not upload anything: no `twine`, no PyPI, no tag.

## Sub-steps

1. **Baseline (15 min).** Run `python3 tools/wheel_check.py` (it builds the wheel, makes a fresh venv, installs the wheel
   and runs it) and record pass/fail. Build the wheel alone (`python3 -m pip wheel . -w /tmp/whl --no-deps
   --no-build-isolation`); record its bytes, the file count, the installed bytes (`du -sb` of the installed `ail_lang`
   directory) and the 20 biggest files grouped by directory (`python/pkg-v12/*.py`, `ir/`, `language_examples/`,
   `stdlib/` ...) in `packaging/WHEEL_REPORT.md`. Commit, push, open the PR against `integ`.
2. **Same C from the wheel (25 min).** Write `tools/wheel_same_c.py`: for every `lab/compare/src/*/main.py` and the first
   program (sorted by name) of each `lab/stdlib/<module>/` directory, build it twice with `--syntax python --debug-dir`:
   once with the checkout's `AIL_CURRENT/ail_chatgpt.py`, once with the installed copy
   (`<venv>/lib/python3.*/site-packages/ail_lang/sdk/ail_chatgpt.py`). Run both from a temp copy of the source, with
   `AIL_NO_CACHE=1`, `ulimit -v 1500000`, at most 2 at a time. Compare: same exit code of the build, byte-identical
   `program.c`, same stdout of the built program. A difference is a finding: name the program and the first differing
   line, and find the cause (a missing or extra file in the wheel is the usual one). Record N/28 in the report. Commit.
3. **Fix missing files (15 min).** If step 2 found a file the wheel lacks, add it in `packaging/ail_wheel_backend.py`
   (the second file list there) or show why it must come through `ail_sdk.py` and write that as a finding (do not edit
   `ail_sdk.py` in this job if the SDK tests would change). Re-run step 2. Commit.
4. **Size (15 min).** For each file group a user never needs at run time, prove it: `git grep -n <file name>` in
   `AIL_CURRENT/*.py` and `AIL_CURRENT/python/pkg-v12/` finds no reader outside tests, AND step 2 still gives the same
   N with the group left out of the wheel. Candidates to check: `python/pkg-v12/test_all.py`, `test_pipeline.py`,
   `language_examples/*.baseline.c` and other `*_reference*.c` / `*_host.c` files (about 0.8 MB). Leave out only
   proven groups, in `ail_wheel_backend.py`, never in the SDK export. Record before/after wheel and installed bytes.
   Add a check to `test_ail_packaging.py` that the left-out names are absent from the wheel and that `wheel_check.py`
   still passes. Run `python3 tools/par_check.py -j 2 test_ail_packaging test_ail_sdk`. Push.

## Done-check

`packaging/WHEEL_REPORT.md` has the size table before/after and N/28 same-C; `tools/wheel_check.py` passes; 20 shards
pass.

## Stop rule

If `pip wheel` or the venv cannot be made on the runner in 15 minutes, stop and report the error text. If a group's
removal changes any step-2 result, put it back. Stop at 80 minutes; push what is done.

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
