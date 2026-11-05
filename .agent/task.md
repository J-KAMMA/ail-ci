Lane: race

# races3: a parallel compare task, and AIL's thread speedup against C, Rust and Go on it

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on races2 (merged, or its branch as your one stacked base).

**Number this moves:** AIL's wall-time speedup from 1 to 4 threads on a new parallel task, `par_collatz`, on the
4-core GitHub runner, and AIL's 4-thread wall time against Rust's. Today neither exists: no compare task uses
threads. The target is a speedup of at least 2.5x, and AIL within 1.5x of Rust on wall time, or a report of where
the time goes.

Base: `origin/integ`. Files you may create or edit, and no others:
- `lab/compare/src/par_collatz/typed.py`, `main.py`, `main.c`, `main.rs`, `main.go` (new; `main.nim` too if Nim's
  threads build with the pinned toolchain without new flags, otherwise leave Nim out and say so);
- `lab/compare/tasks/par_collatz/spec.md`, `gen.py`, `reference.py` (new; copy the layout of an existing task);
- `lab/race/SPEEDUP.md` (new);
- `lab/compare/run_task.py`, only to read a `threads` field from the task's `spec.md` or `gen.py` and set
  `AIL_THREADS` and each language's thread count from it. Every existing task must run exactly as before.

## The task (every language runs the same algorithm: owner decision 2026-11-02)

Input: `N` and `W` on stdin. For every `n` in `1..N`, compute the Collatz step count of `n` (int64; for the
perf input the largest value reached stays far below 2^63, and `gen.py` asserts it). Fill a results array of `N`
entries using `W` workers, each `n` computed exactly once, then, sequentially: print the largest step count, the
smallest `n` that reaches it, and the sum of all step counts. The perf input takes about 1 s per thread in C at
`W=1` (pick `N` so). The public cases include `N=1`, `W > N`, and `W=1`.
- `typed.py` and `main.py`: `concurrent.futures.ThreadPoolExecutor(max_workers=W).map(steps, range(1, N + 1))`,
  or the shape `typedpar.py` lowers (see `docs/design/TYPED_PARALLEL.md`). Both must reach the typed parallel path:
  check that the build prints no `general path` note. CPython runs `main.py` under its GIL, which is the point of
  the column;
- `main.c`: pthreads, contiguous chunks; `main.rs`: `std::thread::scope` and `chunks_mut`, no crates;
  `main.go`: goroutines and a `sync.WaitGroup`.

## Sub-steps

1. **Task and sources (35 min).** Write the spec, `gen.py`, `reference.py` and the five sources. Run
   `python3 lab/compare/run_task.py --task par_collatz --smoke --out /tmp/r.json` for the installed languages.
   Every source must match `reference.py` on all public and hidden cases. Commit, push, open the PR against `integ`.
2. **Thread control (15 min).** The `threads` field in `run_task.py`. Check that the ten existing tasks' commands
   are unchanged (print the command lists before and after for one task). Commit and push.
3. **Measure (30 min).** On the laptop, instruction counts (`tools/icount.c`) of AIL at `W=1` and `W=4`: total
   instructions must not grow by more than 5% (the threads must not add work). Then one run on the runner:
   `gh workflow run compare-lab -R J-KAMMA/ail-ci --ref <your branch> -f tasks='par_collatz'` (one run only; do not
   cancel runs). Write `lab/race/SPEEDUP.md`: wall at `W` = 1, 2, 4 for every language, speedup, AIL against Rust,
   instructions, peak RSS, binary size, compile time. If the speedup is under 2.5x, say where the time goes (thread
   start, chunking, the results list, the sequential tail), with the numbers. Commit, push, wait for CI.

## Done-check

- All sources match `reference.py` on every case.
- `SPEEDUP.md` has the table, and AIL's speedup at 4 threads and its ratio to Rust are stated as numbers.
- The ten existing tasks' commands are unchanged.
- The 20 shards pass.

## Owner decision before merge

A new directory in `lab/compare/src/` joins the daily compare-lab table, which today reports "x/10". Do not change
anything to avoid that; write in the PR and the report that merging adds an 11th row, and that the owner chooses
whether it joins the headline table or moves to its own directory.

## Stop rule

Stop and report if `typed.py` cannot reach the typed parallel path with any Python shape (give the note). Stop when
80 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build.
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
8. Edit only the files this task names; no compiler file. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- `lab/compare/README.md`: layout, `run_task.py`, the `compare-lab` workflow (manual, reads `lab/compare/src` of
  the ref it runs on).
- `AIL_THREADS` sets the worker count of AIL's PAR runtime (`test_ail_parallel_for.py`).
- Laptop wall time swings up to 3x: claim wall time from the runner only.

## Owner decision (2026-11-05)

- **D5** the parallel compare task does not join the headline compare table. Put it in its own folder, outside
  `lab/compare/src` (for example `lab/compare_par/`), so the daily table's "x/10" figures do not change.

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
