Lane: fb-reduce

> Re-run of fbred4_rr1, whose GitHub run was lost (no verdict 6.7 h after dispatch). If its branch job-fbred4_rr1-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.

> Re-run of fbred4, whose GitHub run was lost (no verdict 6.5 h after dispatch). If its branch job-fbred4-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.
Needs: fbred3 races3

# fbred4: reductions at the edges (int64 limits, the probe prefix, exceptions), and the speedup of a parallel sum task

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the 4-thread speedup of a new parallel task `par_sum` on the 4-core GitHub runner, and AIL's
4-thread wall time against Rust's. Targets: speedup at least 2.5x; AIL within 1.5x of Rust; AIL's total instructions at
4 threads at most 1.05x those at 1 thread; at 1 thread at most 1.15x the sequential twin. Also 0 wrong outputs on 12 new
edge probes.

**The task (D5: outside the headline table).** `lab/compare_par/par_sum/`, laid out like races3's `par_collatz` (in
`lab/compare_par/`, or wherever races3's owner decision put it). Input `N` on stdin; the program prints
the sum over `n` in `1..N` of `steps(n) * (n % 7 - 3)`, where `steps` is races3's Collatz step count. `typed.py` and
`main.py` write it as `total = sum(ex.map(term, range(1, N + 1)))` with a `ThreadPoolExecutor`, the shape fbred3 lowers,
so the source also runs on CPython; C uses pthreads, Rust `std::thread::scope`, Go goroutines, each with per-thread
partial sums. Every language runs the same algorithm (owner
decision 2026-11-02). The perf input takes about 1 s per thread in C at 1 thread.

**Edge probes (`lab/race/reduce/edge_*.py`).** An `acc` that starts at `INT64_MAX` and adds 0s then 1; one that starts
at `INT64_MIN` and subtracts; `acc -= e` where `e` reaches `INT64_MIN`; an overflow inside the probe prefix (the first
iterations, before the region goes wide); an overflow inside the last chunk; chunks of one iteration (`N` equal to the
thread count); an exception raised in a function called by `e`; `acc` read after a caught overflow; 16 threads on 3
items; and a reduction in a function called twice. Each is compared with its sequential twin at 1, 2, 4 and 16 threads.

Base: `origin/integ`. Files you may create or edit, and no others:
- `lab/compare_par/par_sum/` (new: `typed.py`, `main.py`, `main.c`, `main.rs`, `main.go`, `spec.md`, `gen.py`,
  `reference.py`);
- `lab/race/reduce/edge_*.py` (new), `lab/race/reduce/RESULTS.md`, `lab/race/SPEEDUP.md`;
- fixes, if an edge probe fails, in the files fbred3 edited, within its line limits;
- the manifest files that `tools/update_manifest.py` writes.

## Sub-steps

1. **Edge probes (20 min).** Write and run them; fix what fails. Commit, push, open the PR against `integ`.
2. **The task (25 min).** Sources, `gen.py`, `reference.py`; every source matches `reference.py` on every case, with a
   public case where the sum would overflow int64 (AIL stops, as its sequential twin does; `reference.py` gives the
   exact value and `spec.md` says that this case is excluded from the timing). Commit and push.
3. **Measure (15 min).** Instructions on the laptop at 1 and 4 threads; one runner run of the compare-lab workflow for
   this task (do not cancel runs). Write the table in `SPEEDUP.md`. Commit, push, wait for CI.

## Done-check

- 12/12 edge probes match their twins at every thread count.
- `SPEEDUP.md` states the speedup, the ratio to Rust, instructions, peak RSS and binary size as numbers.
- The 20 shards pass.

## Stop rule

Stop on any wrong output. Record it first. Stop when 60 minutes pass. Push what is done first.

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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `pyc.py`, `buildcache.py`, `pyboxed2.py`,
   `optlib.py`, `ir/passes/*` or `packaging/ail_lang/cli.py`. Do not edit `DEVLOG.md`.

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
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
