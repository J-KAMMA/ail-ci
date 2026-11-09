Lane: fb-reduce
Needs: fbred4

# fbfsum1: an opt-in parallel float sum with a fixed chunk order that is the same at every thread count (D2 option b)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

First check `lab/race/RESULTS.md` on `origin/integ`: if races2 already landed D2, report NOCHANGE and stop.

**Number this moves:** fixed-order float probes whose printed result (`repr`) is bit-identical at `AIL_THREADS` 1, 2,
4 and 16 and over 5 runs each. The target is 100%. Without the opt-in, a float `acc += e` stays refused exactly as
today, and `program.c` is byte-identical to the base for every program. Also the 4-thread speedup of a float sum bench
on the runner: at least 2.5x.

**The rule.** With the opt-in, `acc += e` on a float `acc` in a parallel body (the same shape as fbred3's int case)
sums in fixed chunks of 4096 iterations whose layout depends only on the iteration count, never on the thread count.
Each chunk starts from `-0.0` (the IEEE identity: `-0.0 + x == x` for every `x`, including `+0.0` and `-0.0`) and adds
left to right; then `acc` adds the chunk sums left to right in chunk order. NaN and infinities flow as in any IEEE sum.
The result is deterministic but not CPython's last bits; `docs/DIFFERENCES.md` gets one entry saying so.

**The opt-in.** The compile-time environment variable `AIL_PAR_FSUM=fixed`, read in `parallel.py`, unless the owner has
chosen another spelling in `docs/design/PAR_REDUCE.md` by the time you start (check). Do not touch the CLI files.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/parallel.py`, the `PARRED` part of `cruntime.py` (a float variant), fbred3's
  `_par_for` hook in `pyfunc.py` (at most 20 more lines; rebase on `origin/integ` just before each push);
- `lab/race/fsum/*.py` (new probes, at least 8: ordinary values, cancellation such as `1e16, 1.0, -1e16`, NaN, inf,
  all `-0.0`, `n` below, at and above 4096, 16 threads on 3 items), `lab/race/fsum/RESULTS.md` (new);
- `AIL_CURRENT/test_ail_par_fsum.py` (new), `AIL_CURRENT/tests.d/test_ail_par_fsum.txt` (new), `docs/DIFFERENCES.md`;
- the manifest files that `tools/update_manifest.py` writes.

## Sub-steps

1. **Probes and the reference order (15 min).** A Python function that computes the fixed order exactly; every probe's
   expected output comes from it. Commit, push, open the PR against `integ`.
2. **Lowering (30 min).** Opt-in check, float partials, combine. Compare every probe at the four thread counts, five runs
   each, against the reference order. Commit and push.
3. **Verify (15 min).** The hash check without the opt-in; the bench speedup (laptop instructions, one runner run);
   `RESULTS.md`; the DIFFERENCES entry. Commit, push, wait for CI.

## Done-check

- 100% bit-identical results across thread counts and runs, equal to the reference order.
- Without the opt-in, the refusal text and `program.c` are unchanged.
- The 20 shards pass.

## Stop rule

Stop on any result that differs between thread counts or runs. Record it first. Stop when 60 minutes pass. Push what is
done first.

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
