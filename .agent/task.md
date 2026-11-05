Lane: safebnd

# safebnd1: the bounds-safety suite: every out-of-range index stops loudly, on the typed, general and hybrid builds

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** cells of the bounds table in `lab/safety/bounds/RESULTS.md` that are `match` (see "The build
modes"). Today there is no such table: the 0.1 claim "safe binaries" has no number behind it for indexing. The target is
24 programs x 4 modes = 96 classified cells, with 0 `silent-wrong` and 0 `crash` cells, or each such cell filed as a
follow-up with a repro. A probe on 2026-11-05 got `IndexError: list index out of range` from `xs[5]` on a 3-item list in
the typed, default and general builds.

Base: `origin/integ`. Files you may create or edit, and no others:
- `lab/safety/bounds/*.py` (24 new programs), `lab/safety/bounds/run.py` (new), `lab/safety/bounds/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_safety_bounds.py` (new) and `AIL_CURRENT/tests.d/test_ail_safety_bounds.txt` (new, one line:
  `test_ail_safety_bounds`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit any compiler file: not `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
`ir/*`, `parallel.py`, `typedpar.py`, `ail_chatgpt.py`, `buildcache.py` or `cli.py`. This job measures and files; it never fixes the compiler.

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

1. **Programs (20 min).** Write 24 programs in `lab/safety/bounds/`, each 8-30 lines of ordinary annotated Python 3.12.
   Each one does some correct work first and prints it, then makes one bad access that is not caught. Cover:
   - list read and write past the end, at `len(xs)` and at `-len(xs) - 1`; a 2-D list row and column;
   - `str`, `bytes`, `bytearray` and `tuple` indexing past the end;
   - an index that comes from `int(text)` and one computed in a `while i <= len(xs)` off-by-one loop;
   - `list.pop()` on an empty list, `pop(i)` out of range, `del xs[i]` out of range;
   - an index past the end of a list held in a class field, and of a list passed to a function;
   - `dict` `KeyError` on a missing str key and on a missing int key;
   - `list.index` and `str.index` of a missing value (`ValueError`);
   - `collections.deque().pop()` on an empty deque, `heapq.heappop([])`;
   - a slice that is out of range (no error in CPython: it must print the same, not stop);
   - an index of 2**40 and one of -(2**62).
   Check each with `python3` first. Commit, push, and open the PR against `integ`.
2. **Runner and table (25 min).** Write `lab/safety/bounds/run.py`: it builds every program in the four modes, runs it,
   classifies it, and writes `RESULTS.md`: one row per program, one column per mode, a totals row per class, the integ
   commit and the date. Run it. Commit and push.
3. **Follow-ups (10 min).** For every `silent-wrong`, `crash` or `stop-differs` cell, add a "Follow-ups" entry in
   `RESULTS.md`: the program, the mode, the CPython last line and what AIL did. Commit and push.
4. **Ratchet test (20 min).** Write `AIL_CURRENT/test_ail_safety_bounds.py`. It builds every program that is `match` in
   the default and general modes and checks that it still matches. It skips when there is no C compiler. Register it
   (Appendix A rule 6) and run it. Commit, push, and wait for CI.

## Done-check

- `RESULTS.md` has 24 rows and 96 classified cells, and its totals add up to 96.
- Every `silent-wrong` and `crash` cell has a follow-up entry with a repro.
- `python3 AIL_CURRENT/test_ail_safety_bounds.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

A `silent-wrong` cell is the most important finding: record it with its repro, commit, push, and report it at once,
then go on with the table. Stop if the runner cannot build in two of the four modes; give the exact error. Stop when 80
minutes pass. Push what is done first.

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
