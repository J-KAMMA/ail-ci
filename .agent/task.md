Lane: safestop

# safestop1: the runtime-stop suite: division by zero, deep recursion and bad conversions stop like CPython

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** cells of the runtime-stop table in `lab/safety/stops/RESULTS.md` that are `match`. The target is
20 programs x 4 modes = 80 classified cells, with every `crash` cell filed as a follow-up. A probe on 2026-11-05: a
two-line infinite recursion printed `RecursionError: maximum recursion depth exceeded` in the typed and default builds,
but printed nothing with `AIL_UNIFIED_FORCE=1` (the general path). Confirm that case first; it is the likeliest `crash`.

Base: `origin/integ`. Files you may create or edit, and no others:
- `lab/safety/stops/*.py` (20 new programs), `lab/safety/stops/run.py` (new), `lab/safety/stops/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_safety_stops.py` (new) and `AIL_CURRENT/tests.d/test_ail_safety_stops.txt` (new, one line:
  `test_ail_safety_stops`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit any compiler file: not `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
`ir/*`, `parallel.py`, `typedpar.py`, `ail_chatgpt.py`, `buildcache.py` or `cli.py`. This job measures and files; it never fixes the compiler. Index errors and int overflow belong to other suites;
leave them out.

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

## Sub-steps

1. **Programs (20 min).** Write 20 programs in `lab/safety/stops/`, each 6-30 lines of ordinary annotated Python 3.12.
   Each prints some correct values first, then hits one uncaught error. Cover:
   - `ZeroDivisionError` from `//`, `%`, `/` on ints, `/` on floats, `divmod(x, 0)`, where the zero comes from input text;
   - `RecursionError`: direct infinite recursion; mutual recursion; recursion through a method; a recursion 5000 deep
     that CPython refuses but that only needs a little stack;
   - `ValueError`: `int("x")`, `int("")`, `float("abc")`, `chr(-1)`, `math.sqrt(-1)`, `math.log(0)`;
   - `OverflowError` from `int(float("inf"))` and `ValueError` from `int(float("nan"))`;
   - `UnicodeDecodeError` from `b"\xff".decode("utf-8")`;
   - `StopIteration` from `next()` on an empty iterator; a failing `assert` with a message.
   Check each with `python3` first. Commit, push, and open the PR against `integ`.
2. **Runner and table (25 min).** Write `run.py` (build, run, classify, write `RESULTS.md` with one row per program, one
   column per mode, totals per class, the integ commit and the date). Run it. Commit and push.
3. **Follow-ups (10 min).** For each `crash`, `silent-wrong` or `stop-differs` cell, add a "Follow-ups" entry with the
   program, the mode, the exit status or signal, CPython's last line and AIL's. Commit and push.
4. **Ratchet test (20 min).** Write `AIL_CURRENT/test_ail_safety_stops.py`: it builds the programs that are `match` in the
   default and general modes and checks that they stay so. It skips when there is no C compiler. Register it (Appendix A
   rule 6) and run it. Commit, push, and wait for CI.

## Done-check

- `RESULTS.md` has 20 rows and 80 classified cells, and its totals add up to 80.
- Every `crash` and `silent-wrong` cell has a follow-up entry with a repro.
- `python3 AIL_CURRENT/test_ail_safety_stops.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Record a `silent-wrong` cell with its repro, commit, push, and report it at once, then go on. Stop if the runner cannot
build in two of the modes; give the exact error. Stop when 80 minutes pass. Push what is done first.

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
