Lane: fb-reduce
Needs: races2

# fbred1: the exact shared-int reduction (D1 option c): design note, a Python reference model, and probes (no compiler change)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** differences between the reference model of the parallel combine and a sequential simulation, on
200,000 random cases. The target is 0 differences in (the iteration where the run stops, the exception kind, the final
accumulator). Also: the count of programs in `lab/race/` and the first 500 `lab/corpus/programs` refused today because
of a shared int `+=` in a parallel body or a `sum(...map...)` over a parallel map. That is the count fbred3 moves.

**The design to write down in `docs/design/PAR_REDUCE.md`.**
- Shape, v1: in a parallel body (`par_range`, the `_ail_pmap` loop, the `Thread`-k loop), a statement `acc += e` or
  `acc -= e`, where `acc` is an int local of the enclosing function assigned before the loop and `e` is an int
  expression the ownership proof accepts. `acc` is not read or written anywhere else in the body. Several accumulators
  are allowed. The rest of the body writes only its own locals: a body that also writes `xs[i]` stays refused in v1,
  because an overflow caught by a `try` (here or in any caller) would show writes made by iterations after the point
  where the sequential loop stops.
- Also `acc = sum(ex.map(f, xs))` and `sum(pool.map(f, xs))`. Here the order differs: the map finishes first, so the
  first exception from `f` in iteration order wins over any overflow, and only then does the sum stop at its first
  overflowing prefix.
- Per chunk `c` (a contiguous index range fixed by the runtime): the partial sum `S_c`, the largest prefix `M_c` and
  the smallest prefix `m_c` (over prefixes of length 1 and more), all in `__int128`, and the chunk's first exception. A
  chunk stops at its first exception, so `S_c`, `M_c` and `m_c` cover only the iterations before it.
- The combine runs on the calling thread in chunk order, starting from `B`, the value of `acc` before the loop. For each
  chunk: if `B + M_c > INT64_MAX` or `B + m_c < INT64_MIN`, the sequential loop stops inside `c`: re-run `c` alone,
  sequentially, from `B`, with the ordinary checked int64 add, so it stops at the same iteration with the same
  OverflowError text. Otherwise, if `c` has an exception, raise it. Otherwise `B += S_c`. At the end, `acc = B`.
- Why it is exact: `B` is exactly the sequential prefix at the start of `c`; the sequential loop leaves int64 inside `c`
  if and only if some prefix of `c` does, which happens if and only if the largest or the smallest one does. `__int128`
  cannot overflow: at most 2^63 terms of at most 2^63 each is at most 2^126.
- The re-run is possible because `e` may call only the pure int/float functions the proof already requires. It costs
  at most one chunk.
- A caught overflow leaves `acc` at the last prefix that fit, as in the sequential loop. The loop variable after the
  loop behaves as `parallel.py` makes it behave today; if a read after the loop is not supported now, it stays refused.
- The probe prefix that `ail_par_run` runs on the calling thread adds into `acc` sequentially with the checked add; the
  wide phase starts from that `B`.
- Cost: per iteration, one 128-bit add and two compare-and-moves. Target for fbred2: at most 1.15x the sequential
  loop's instructions at `AIL_THREADS=1`.

Base: `origin/integ`. Files you may create, and no others:
- `docs/design/PAR_REDUCE.md` (new)
- `lab/race/reduce/model.py` (new): the combine and a sequential simulator, with the random test
- `lab/race/reduce/*.py` (new probes, at least 14) and `lab/race/reduce/EXPECTED.md` (new)

## Sub-steps

1. **Model (25 min).** `model.py`: random chunkings (including chunks of length 1 and one chunk), values near 0, near
   +-2^62 and at +-2^63, patterns `+big, +big, -big` (stops) and `-big, +big` (fits), an exception at a random
   iteration before or after the overflow point, and the `sum(map)` order. 200,000 cases, fixed seed, 0 differences.
   Commit, push, open the PR against `integ`.
2. **Probes (20 min).** At least 14 programs: small sum, negative sum, a total that fits while a prefix does not (must
   stop), overflow at the first and at the last iteration, an exception before and after the overflow point, a `try`
   that catches the overflow and prints `acc`, two accumulators, `sum(ex.map(...))` with an exception after the
   overflow index, `n = 0`, `n = 1`, more workers than items. For each, the expected output is that of its sequential
   twin (`range` instead of the parallel shape) in the default AIL build; where nothing overflows it must also equal
   CPython. Write the expected outputs in `EXPECTED.md`. Commit and push.
3. **Design note and count (15 min).** `PAR_REDUCE.md` with the design above, the proof sketch, and the refused-today
   count. Commit, push, wait for CI.

## Done-check

- `python3 lab/race/reduce/model.py` prints 0 differences on 200,000 cases.
- At least 14 probes with expected outputs taken from their sequential twins.
- `PAR_REDUCE.md` holds the design, the proof sketch and the count; `git diff --stat origin/integ` shows only the
  files above; the 20 shards pass.

## Stop rule

Stop if the model shows any difference that the design cannot remove. Write the counterexample into `PAR_REDUCE.md`
first. Stop when 60 minutes pass. Push what is done first.

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
8. Edit no compiler or runtime file. Do not edit `DEVLOG.md`.

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
