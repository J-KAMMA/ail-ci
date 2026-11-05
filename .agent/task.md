Lane: safeovf

# safeovf1: the overflow-safety suite: int64 overflow stops loudly or matches CPython, on every build

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** cells of the overflow table in `lab/safety/overflow/RESULTS.md` that are `match` or `ovf-stop`.
Ints are int64 by default and overflow must stop loudly (owner decision 2026-10-31). No table proves it across the
builds today. The target is 24 programs x 5 modes = 120 classified cells, with 0 `silent-wrong` and 0 `crash` cells, or
each such cell filed as a follow-up. A probe on 2026-11-05 of `9223372036854775807 + 1` printed
`OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)` in the typed, default and
general builds, where CPython prints `9223372036854775808`.

Base: `origin/integ`. Files you may create or edit, and no others:
- `lab/safety/overflow/*.py` (24 new programs), `lab/safety/overflow/run.py` (new), `lab/safety/overflow/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_safety_overflow.py` (new) and `AIL_CURRENT/tests.d/test_ail_safety_overflow.txt` (new, one
  line: `test_ail_safety_overflow`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit any compiler file: not `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
`ir/*`, `parallel.py`, `typedpar.py`, `ail_chatgpt.py`, `buildcache.py` or `cli.py`. This job measures and files; it never fixes the compiler. Do not repeat `test_ail_int64_default.py`,
`test_ail_int64_edges.py` or `test_ail_overflow_error.py`: read them first and pick cases they do not cover.

## The build modes

Each program is built four ways where this task says so. Use a fresh `-o` path each time.
- **typed**: `python3 -B AIL_CURRENT/ail_chatgpt.py compile P.py -o OUT --strict` (a refusal counts as `refused`);
- **default**: the same command without `--strict`;
- **general**: `AIL_UNIFIED_FORCE=1 python3 -B AIL_CURRENT/ail_chatgpt.py compile P.py -o OUT`;
- **hybrid**: `python3 -B AIL_CURRENT/ail_chatgpt.py build --cpython P.py -o OUT`. Read
  `AIL_CURRENT/test_ail_cpython_hybrid.py` for how the result is run. If the hybrid build does not work on the runner
  (no `Python.h`), mark the whole column `n/a` with the exact error and go on.

Run every binary under `ulimit -v 1500000` and `timeout 20`. Classify each run against `python3 P.py`:
- `match`: stdout, the exit status and the last stderr line equal CPython's;
- `stop-differs`: both stop with a nonzero status, but the last stderr line differs (give both lines);
- `silent-wrong`: the exit status is 0 or stdout differs, and CPython stopped, or the other way round;
- `crash`: killed by a signal (exit status 128 or more, or a negative return code), or the timeout hit;
- `refused`: the build refused.

A fifth mode, **exact**: the default command plus `--exact-int`. It must be `match` in every row.
One more class, `ovf-stop`: CPython prints a result, and AIL exits with status 1 and a last stderr line that starts with
`OverflowError: integer overflow`, with nothing wrong printed on stdout before it. `ovf-stop` counts as safe.

## Sub-steps

1. **Programs (20 min).** Write 24 programs in `lab/safety/overflow/`, each 8-30 lines of ordinary annotated Python 3.12.
   Each prints some correct values first, then one value whose exact result is beyond int64. Cover:
   - `+`, `-`, `*` at both ends of int64; `-x` and `abs(x)` of `-9223372036854775808`;
   - `-9223372036854775808 // -1` and `% -1`, `divmod` of the same;
   - `2 ** 63`, `pow(3, 40)`, `1 << 63`, `1 << 64`, `x << 1` in a loop;
   - `+=` and `*=` in a loop on a local, on a class field, on a dict value and on a list item;
   - `sum()` of a list whose total passes int64; `math.factorial(21)`; `math.prod`;
   - `int("99999999999999999999")`, `int("-9223372036854775809")`, `int(1e19)`, `round(1e19)`;
   - a Fibonacci loop that passes int64 at step 93;
   - a value that passes int64 and comes back into range before it is printed (`(x * 4) // 4`).
   Check each with `python3` first. Commit, push, and open the PR against `integ`.
2. **Runner and table (25 min).** Write `run.py`: it builds every program in the five modes, runs it, classifies it, and
   writes `RESULTS.md`: one row per program, one column per mode, a totals row per class, the integ commit and the date.
   Run it. Commit and push.
3. **Follow-ups (10 min).** For every `silent-wrong`, `crash` or `stop-differs` cell, and every `exact` cell that is not
   `match`, add a "Follow-ups" entry: the program, the mode, CPython's output and AIL's. Commit and push.
4. **Ratchet test (20 min).** Write `AIL_CURRENT/test_ail_safety_overflow.py`: it builds the programs that are `match` or
   `ovf-stop` in the default and exact modes and checks that they stay so. It skips when there is no C compiler.
   Register it (Appendix A rule 6) and run it. Commit, push, and wait for CI.

## Done-check

- `RESULTS.md` has 24 rows and 120 classified cells, and its totals add up to 120.
- Every `silent-wrong` and `crash` cell has a follow-up entry with a repro.
- `python3 AIL_CURRENT/test_ail_safety_overflow.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

A `silent-wrong` cell is the most important finding: record it with its repro, commit, push, and report it at once,
then go on. Stop if the runner cannot build in two of the modes; give the exact error. Stop when 80 minutes pass. Push
what is done first.

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
