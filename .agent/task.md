Lane: fb-pmap
Needs: races3

# fbpmap1: where parallel-map time goes on par_collatz and on uneven loads: blocks, probe prefix, tail, results list (measure only)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** `lab/race/PMAP.md`, unknown today: for races3's `par_collatz` and 4 synthetic loads, at 1, 2 and
4 threads, the idle tail (time from the first worker running out of blocks to the region's end, as a share of the
region's wall time), the probe-prefix time, the number of blocks, and the time to write the results list. It decides
fbpmap2:
- guided chunk sizes: go if the idle tail is at least 10% of region wall time on at least 2 loads at 4 threads;
- work-stealing deques (Chase-Lev): they pay only for nested regions, which today run sequentially (`ail_par_cur`).
  Count programs in `lab/`, `lab/corpus/programs` and the tests whose parallel region calls into another one. Go only
  if at least 3 do; otherwise write "no-go: no nesting" and leave it.

**The loads (`lab/race/pmap/*.py`).** Uniform cost; a linear ramp (iteration `i` costs about `i`); one heavy block (1%
of the iterations cost 100x, placed at the end); a tiny body over 10M iterations. Each prints a checksum and matches
CPython.

Base: `origin/integ`. Files you may create, and no others:
- `lab/race/PMAP.md`, `lab/race/PMAP.json`, `lab/race/pmap/*.py`, `lab/race/pmap/run.py` (new)

## Sub-steps

1. **Loads and timers (25 min).** Write the loads. Time each block in a scratch copy of `program.c` only (an
   `ail_par_now()` stamp at block start and end, per worker; a sed on the scratch copy, never the compiler). Check that
   the timed build prints exactly what the plain build prints. Commit, push, open the PR against `integ`.
2. **Measure (25 min).** On the laptop at up to 4 threads under `ulimit -v 1500000`: wall time median of 5 (noisy; say
   so), instructions, and the block timeline. For `par_collatz`, one runner run of the compare-lab workflow for that task
   at 1, 2 and 4 threads (do not cancel runs), next to races3's C and Rust numbers. Commit and push.
3. **Price (10 min).** Both go/no-go lines and the nesting count. Commit, push, wait for CI.

## Done-check

- 5 loads (par_collatz and 4 synthetic), each with the idle tail, probe time, block count and results-list time at
  1, 2 and 4 threads.
- Both go/no-go lines are written; `git diff --stat origin/integ` shows only `lab/race/`; the 20 shards pass.

## Stop rule

Stop on any wrong output in a timed build. Record it first. Stop when 60 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
   Measurements above about 1 GB go to GitHub or are skipped. Run TSan and ASan builds one at a time.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Edit no file outside `lab/race/`. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet. A fallback to the general path prints `note: ... built on the general
  path ...` on stderr. For a `program.c` hash check use `--debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly with OverflowError.
  Silent wrong output is never allowed.
- Instruction counts: `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
  `/tmp/icount ./program < input`. They repeat to 1e-7; wall time on the laptop swings up to 3x. rc1 ran where
  `perf_event_open` failed (no PMU). If that happens, say so and use `valgrind --tool=callgrind` `Ir` on a smaller
  input for every go/no-go number; never a gcov estimate.
- Peak RSS: `/usr/bin/time -v` "Maximum resident set size", median of 3 (`lab/compare/run_task.py` does the same);
  `tools/rss_phases.py` splits a run into phases.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where the task says so.
- Parallel runtime: `cruntime.py` parts `PAR` (`ail_par_run`, `ail_par_go_wide`, `ail_par_work`, ~line 30700-30960)
  and `PARN` (`ail_par_run_n`). Blocks are `n / (threads * 8)` iterations handed out by an atomic counter; the lowest
  failing block's exception wins (`fail_block`); before going wide the calling thread runs a doubling probe prefix
  (`AIL_PAR_PROBE_NS`). `PARN` patches the `PAR` text through `_PAR_CAPPED_EDITS`, which asserts each old string
  occurs exactly once: an edit to `PAR` must keep those strings or update the list. Regions do not nest
  (`ail_par_cur`): an inner region runs sequentially.
- `parallel.py` holds the ownership proof, `typedpar.py` the map/submit/Thread lowering; read
  `docs/design/TYPED_PARALLEL.md`. `lab/race/run.py` prints the three counts (silent races, safe matched, safe
  GIL-free); races1 measured 0 / 11 of 12 / 11 of 12.
- Owner decisions 2026-11-05 (races2): D1 shared int `+=` refused now, exact semantics later as their own job; D2 float
  sum only behind an explicit opt-in, fixed chunk order; D3 appends into per-chunk buffers joined in iteration order,
  equal to the sequential result; D4 a hybrid native call taking a container keeps the GIL; D5 parallel compare tasks
  stay out of the headline table (`lab/compare_par/`).
- `AIL_THREADS` is read once per process, clamped to 1..256.

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
