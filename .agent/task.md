Lane: pyperf

# pyperf1: a pyperformance-style subset (10 benchmarks) built by AIL from plain Python, a headline number versus CPython

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the P1 claim "write Python, get a fast binary", measured on programs nobody wrote for AIL.
Today AIL has no number on the classic CPython benchmark kernels. Target: 10 programs in `lab/pyperf/bench/`, each the
algorithm of a pyperformance benchmark; at least 8/10 build in the default mode and print what CPython prints; and
`RESULTS.md` gives, per program, typed/general/refused, the instruction-count ratio CPython/AIL, and the geomean over
the programs that match. The programs are plain Python 3.12 with no AIL-specific spelling, so the number is honest.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `lab/pyperf/bench/{nbody,fannkuch,spectral_norm,nqueens,float_bench,richards,raytrace,generators,scimark_sor,scimark_fft}.py`
- `lab/pyperf/run.py`, `lab/pyperf/README.md`, `lab/pyperf/RESULTS.md`
- `AIL_CURRENT/test_ail_pyperf_lab.py` and `AIL_CURRENT/tests.d/test_ail_pyperf_lab.txt` (one line:
  `test_ail_pyperf_lab`)
- the manifest files that `tools/update_manifest.py` writes
No compiler or runtime file is edited. A refusal or a slow program is recorded, not fixed.

## Sub-steps

1. **Programs (30 min).** Write the 10 programs from the published algorithms (pyperformance is MIT; write each one
   yourself from the algorithm, do not paste its files). Rules for every program:
   - plain Python 3.12, top-level `main()` call, no annotations beyond what an ordinary user writes, no `import` other
     than `sys`, `math` (and nothing for `generators`);
   - a size read from `sys.argv[1]` when given, with a default that makes CPython run 1-3 s on this laptop;
   - deterministic output: one or a few lines with a checksum or the final values, floats printed with `repr` or a
     fixed `"%.9f"` format;
   - 30-200 lines. `richards` and `raytrace` keep their classes (that is the point of those two).
   Check each with `python3` at the default and at a small size (for the test). Commit, push, and open the PR against
   `integ`.
2. **Runner (15 min).** Write `lab/pyperf/run.py`. For each program: build with the default command in a temp dir
   (`AIL_NO_CACHE=1`, `ulimit -v 1500000`, timeout 300 s, one build at a time); record typed/general/refused and the
   first refusal or the `note: ... general path` line; run AIL and `python3` at the default size and compare stdout
   and exit status; measure instructions of both with `tools/icount.c` (build it as its header comment says) and wall
   time as the median of 3. `--small` runs the small sizes only and skips timing. Output: a JSON file and a markdown
   table. Commit and push.
3. **Measure (20 min).** Run `run.py` on all 10. Also build every program with `AIL_UNIFIED_FORCE=1` and compare
   stdout (record only). Write `RESULTS.md`: date, commit, CPU, the table (program, path, matches, CPython
   instructions, AIL instructions, ratio, wall CPython, wall AIL), the geomean ratio over the matching programs, and
   for each non-typed program the exact first refusal or fallback line as a follow-up. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_pyperf_lab.py` (structure of `AIL_CURRENT/test_ail_std_shlex.py`):
   for every program that matches in `RESULTS.md`, build it and compare stdout and exit status with `python3` at the
   small size, in the default build. Skip when there is no C compiler. Keep it under 3 minutes on one core. Register
   it (Appendix A rule 6), run it, commit, push, and wait for CI.

## Done-check

- At least 8 of the 10 programs build in the default mode and match CPython.
- `RESULTS.md` has the table and the geomean instruction ratio.
- `python3 AIL_CURRENT/test_ail_pyperf_lab.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if fewer than 5 programs build without editing a compiler file; give each first refusal line. Stop if
`icount` cannot read the counter (perf_event denied); then use wall time only and say so. Stop when 80 minutes pass.
Push what is done first.

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
