Lane: tccprobe
Needs: tccprobe1

> Re-run of devcc1: the first run stopped because tccprobe1 was not merged. This copy sits in lane tccprobe, so it starts only after tccprobe1 (and its FIX continuation) integrates. If lab/tccprobe/RESULTS.md is still missing on origin/integ, stop and report again.

# devcc1: can MIR's c2m compile AIL's generated C with gcc-identical output, and how fast? (measure only)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on tccprobe1 (lane `tccprobe`) merged into `integ`: reuse its `lab/tccprobe/run.py` harness, its 50-program
corpus and its failure buckets in `lab/tccprobe/RESULTS.md`. If it is not merged, stop and report.

**Owner decision 2026-11-05:** a fast dev C compiler is allowed only as an explicit opt-in (`--cc=mir`, `--cc=tcc` or
a dev flag). Release and default builds stay on gcc `-O2`. Its output must be byte-identical to the gcc build on the
test corpus, or the mode refuses that program. This job only measures; it changes no compiler file.

**Numbers this produces** (unknown today), for c2m next to tccprobe1's tcc numbers:
- (a) programs whose generated C c2m accepts, out of tccprobe1's 50;
- (b) of those, programs whose stdout, stderr and exit status are byte-identical to the gcc `-O2` build;
- (c) median C-compile time of c2m against gcc `-O2` (tccprobe1 has tcc's);
- (d) median run time and run instructions against the gcc `-O2` build.
MIR's own README claims c2m compiles about 80x faster than gcc `-O2` with code at a 0.91 geomean of gcc `-O2` speed:
that is a claim on MIR's benchmarks, not on AIL's C. Price the gain for AIL: the gcc phase is 26.0% of pooled cold
wall (CTIME_2026-11.md), so its Amdahl bound is 1.35x on the whole build; write the achieved compile ratio as a
fraction of that bound.

Base: `origin/integ`. Files you may create, and no others:
- `lab/devcc/run.py` (new; may import `lab/tccprobe/run.py`), `lab/devcc/RESULTS.md` (new)
- `lab/devcc/fail_*.txt`: at most 10 short excerpts

## Sub-steps

1. **Setup (20 min).** Build MIR from a pinned release tag of https://github.com/vnmakarov/mir in `~/scratch/mir`
   (outside the repository; record the tag, commit hash and `c2m -v`). Nothing is vendored. Find how c2m produces a
   runnable program: it executes C in-process (`-eg`, `-el`, `-ei`) and, as far as the survey knows, writes no ELF
   executable. Record which modes exist and how library calls (`libc`, `libm`, `pthread`) are resolved. Also record
   what `PIPE_CC=tcc` and `PIPE_CC=<c2m>` do with the CLI today (`buildcache.py` line ~291 picks `$PIPE_CC`): run one
   program each, say whether gcc-only flags reach them, and whether a wrong output can pass silently today. Commit,
   push, open the PR against `integ`.
2. **Corpus (40 min).** For each of the 50 programs: generate the C once (`--debug-dir`), run it with c2m in the mode
   found in step 1 (`c2m -O2 program.c ... -eg < input`), and compare stdout, stderr and exit status with the gcc
   `-O2` build. Time the C compile and the run, median of 3; run instructions with `tools/icount.c`. Sort failures into
   tccprobe1's buckets plus "no executable output" and "wrong output". Commit and push.
3. **Report (20 min).** `RESULTS.md`: (a)-(d) for c2m beside tcc; buckets with the generated-C construct and the
   emitter or runtime file and line; the price (share 26.0%, bound 1.35x, achieved compile ratio); and a
   recommendation for devcc2: which compiler (`tcc`, `mir`, or both), which programs the mode must refuse (by bucket),
   and whether the mode can produce an executable or only `run`. Commit, push, wait for CI.

## Done-check

- `RESULTS.md` has (a)-(d) for 50/50 programs, the bucket counts and one excerpt per bucket.
- Every wrong-output case is listed with both outputs.
- `git diff --stat origin/integ` shows only files under `lab/devcc/`; the 20 shards pass.

## Stop rule

Wrong output is a stop condition: if a c2m run prints anything different from the gcc `-O2` build, record it in
`RESULTS.md` first (it may be undefined behaviour in the generated C that gcc hides; say which, if you can tell).
Do not change the compiler, the runtime or the default C compiler. Stop when 80 minutes pass. Push what is done first.

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
8. Edit no file outside `lab/devcc/`. Do not edit `DEVLOG.md`. MIR is built in `~/scratch`, never copied into the
   repository (vendoring needs license notices and an owner decision).

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--debug-dir DIR]`. `DIR/program.c` is the
  generated C. The C compile goes through `pyc._cc` (`python/pkg-v12/pyc.py` line ~221) and `buildcache.run_cc`;
  `buildcache.py` line ~291 chooses `$PIPE_CC`, else `cc`, `clang` or `gcc`.
- Licenses: MIR is MIT (code may be copied with a notice); tcc is LGPL-2.1 (run it as an external tool only, never
  vendor it).
- Laptop wall time swings up to 3x. Use instruction counts for run-time claims; C-compile times are ratios within one
  run.

## Owner decision (2026-11-05)

- MIR is used as an external c2m command only. Do not vendor it into the repo.

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
