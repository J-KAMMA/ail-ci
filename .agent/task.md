Lane: colorsys

# colorsys2: `import colorsys` as a bundled AIL module (`AIL_CURRENT/stdlib/colorsys.py`) that stays on the typed path

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** programs in `lab/stdlib/colorsys/` that build in the default mode and print what CPython
prints, with the same exit status. On `integ` today it is 0/12: `colorsys.rgb_to_hsv(...)` is refused with
`not in the subset: colorsys.rgb_to_hsv (not yet published in NAMES_library.json)`. The target is 12/12 matching,
and at least 9/12 on the typed path (no `built on the general path` note). Third number: instructions of a 1M-pixel
conversion loop, AIL against `python3`.

colorsys is all float arithmetic: it is the kind of module where "write Python, get C speed" should hold. A probe on
2026-11-04 found that the typed path refuses a three-argument `max(r, g, b)` (`call to max(); this compiler builds
only the builtins it names`), which CPython's colorsys uses. So the module must be written in the typed subset.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/colorsys.py` (new)
- `lab/stdlib/colorsys/*.py` (12 programs + `bench_pixels.py`) and `lab/stdlib/colorsys/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_colorsys.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_colorsys.txt` (new, one line:
  `test_ail_std_colorsys`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Programs and baseline (15 min).** Write 12 programs in `lab/stdlib/colorsys/`, each 15-40 lines of ordinary
   Python 3.12 with annotated functions. Together they cover all six public functions (`rgb_to_yiq`, `yiq_to_rgb`,
   `rgb_to_hls`, `hls_to_rgb`, `rgb_to_hsv`, `hsv_to_rgb`), round trips over a grid of colours, grey inputs
   (`r == g == b`), the edges 0.0 and 1.0, hue 1.0 and values just below it, negative and above-1 inputs (CPython
   does not clamp), int arguments (`rgb_to_hsv(255, 0, 0)`), a palette generator that formats `#rrggbb` with
   `int(round(x * 255))`, and sorting colours by hue. Print floats with plain `print()` and with `repr()` so every bit
   is compared. Build each with the default command; record typed, general or refused, with the first refusal line,
   in `RESULTS.md` under "Before (integ <short sha>)". Commit, push, and open the PR against `integ`.
2. **The module (20 min).** Write `AIL_CURRENT/stdlib/colorsys.py` from CPython 3.12's `Lib/colorsys.py` (print it
   with `python3 -c "import colorsys, inspect; print(inspect.getsource(colorsys))"`). Keep every float operation in
   the same order, so results are bit-identical. Replace `max(r, g, b)` and `min(r, g, b)` by small helpers with the
   same result: the first largest (or smallest) argument, as CPython's builtin returns. Annotate parameters as
   `float` and returns as `tuple[float, float, float]`. Keep `ONE_THIRD`, `ONE_SIXTH`, `TWO_THIRD` and `__all__`.
   Commit and push.
3. **Make the programs pass, typed (20 min).** Build all 12 again, in the default build and with
   `AIL_UNIFIED_FORCE=1`. Fix the module, never the programs, until 12/12 match and as many as possible are typed.
   For each program still on the general path, record the note's reason in `RESULTS.md`; a reason that needs a
   compiler file is a follow-up with the exact text. Check int arguments: CPython accepts them; the typed build must
   give the same output or fall back to the general path, never stop. Commit and push.
4. **Bench and test (20 min).** Write `lab/stdlib/colorsys/bench_pixels.py`: 1,000,000 pixels from a fixed LCG,
   `rgb_to_hsv` then `hsv_to_rgb`, sum the results, print the sum with `repr()`. It must build typed. Record
   instructions for AIL and for `python3 bench_pixels.py` (Appendix B), binary bytes, and peak RSS. Then write
   `AIL_CURRENT/test_ail_std_colorsys.py`, copying the structure of `AIL_CURRENT/test_ail_std_shlex.py`: it builds every
   program, compares stdout and the exit status with `python3` in both builds, and asserts the typed ones build with
   no general-path note. It skips when there is no C compiler. Register it (Appendix A rule 6), run
   `python3 tools/par_check.py -j 2 test_ail_std_colorsys`, fill `RESULTS.md` under "After". Commit, push, wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_colorsys.py` passes.
- 12/12 programs match CPython in both builds; at least 9/12 are typed; `bench_pixels.py` is typed.
- `RESULTS.md` has the before/after table and the instruction counts.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled `colorsys.py` is not picked up by `import colorsys`; give the exact message. If a result
cannot be made bit-identical, leave that function as CPython wrote it (general path), record why, and go on. Stop
when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (Follow C:\Users\bluec\ail-work\agent-brief-rules.md)

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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not
   edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
- Instruction counts: `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
  `/tmp/icount PROG ARGS`. If `perf_event_open` is refused, use the median of 5 wall times and say so.
  Peak RSS: `/usr/bin/time -v PROG` ("Maximum resident set size").
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
