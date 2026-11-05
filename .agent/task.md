Lane: race

# races2: the smallest rule that makes the race probes pass, and the semantics questions for the owner

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on races1 (merged into `integ`, or its branch `job-races1-*` as your one stacked base). Read
`lab/race/RESULTS.md` and `docs/design/TYPED_PARALLEL.md` first.

**Number this moves:** the three counts of `lab/race/RESULTS.md`. Targets:
- silent races: 0, in the default build and with `AIL_UNIFIED_FORCE=1`;
- safe matched: every safe probe;
- safe GIL-free: today's count plus at least 2, or the report says which rule blocks each safe probe that still
  runs under the lock.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/parallel.py`, `AIL_CURRENT/python/pkg-v12/typedpar.py`;
- `AIL_CURRENT/ail_cpython_hybrid.py` and `AIL_CURRENT/python/pkg-v12/c_api_bridge.py`, only where they decide
  whether a native call releases the GIL;
- `lab/race/*` (probes, runner, `RESULTS.md`), `docs/design/TYPED_PARALLEL.md`;
- `AIL_CURRENT/test_ail_race_probes.py`, and new test methods in `test_ail_parallel_for.py`,
  `test_ail_typed_parallel.py`, `test_ail_cpython_hybrid.py`;
- the manifest files that `tools/update_manifest.py` writes.

Not `pyfunc.py` or `cruntime.py`: the codegen, bce-ranges and pyreach lanes are changing them. If a fix needs
`pyfunc._par_for`/`_par_outline` or cruntime's PAR block, write the exact change into `RESULTS.md` as a follow-up for
this lane and stop that part.

## The rule

Make the smallest change that closes each silent race and keeps every safe probe matching. Prefer, in this order:
1. refuse the lock-free lowering by name, so the program falls back to the general path under the lock, with a
   note that says why and a `write instead:` line. This is always allowed: it is safe and it matches CPython;
2. a compile-time check in `parallel.py`/`typedpar.py`: a parallel body may write shared state only at indexes that
   differ between iterations (the existing proof), and never through a second name, a global or a container method;
3. for the hybrid: keep the GIL during a native call whose arguments include a list, bytearray, dict or object,
   or whose function reads a module-level container. Calls that take and return only ints, floats and str keep
   releasing it. This is the safe default; a faster choice is decision D4 below.

Then raise "safe GIL-free" with shapes the existing proof already covers but `typedpar.py` does not lower (for
example `map` over a `range`, or `submit` + `.result()` in order). Pick the two shapes with the most probes.

## Sub-steps

1. **Close the races (35 min).** One commit per race found by races1. For each, add the probe to the test as a
   normal (not expected-failure) case. If races1 found none, say so, and spend this time on sub-step 2. Commit,
   push, open the PR against `integ`.
2. **More GIL-free shapes (25 min).** Lower the two shapes. Each must give CPython's output at `AIL_THREADS` 1, 2,
   4, 16. Commit and push.
3. **Verify and write the decisions (20 min).**
   - `lab/race/run.py`: the three counts after, both builds, in `RESULTS.md` under "After".
   - Programs that import none of `threading`, `concurrent`, `multiprocessing` and use no `par_range` are
     unchanged: `program.c` hash equal to the base for the 10 `lab/compare/src/*/typed.py` and the first 100
     `lab/corpus/programs` (`--debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`).
   - Run `test_ail_race_probes`, `test_ail_parallel_for`, `test_ail_typed_parallel` (including its TSan and
     ASan/UBSan tests), `test_ail_threads`, `test_ail_ffi_parallel`, `test_ail_cpython_hybrid`,
     `test_ail_examples_hybrid`.
   - Write the owner decisions below into `RESULTS.md` under "Owner decisions", with the probes each one affects and
     what each option costs. Do not build any of them.
   Commit, push, wait for CI.

## Owner decisions (write them up; do not choose)

- **D1. `total += f(i)` on a shared int in a parallel body.** Sequential AIL stops with OverflowError at the first
  prefix sum beyond int64; CPython gives the exact big int. Partial sums per thread can overflow where the
  sequential loop does not, and the other way round.
  (a) keep refusing it: the loop runs under the lock, or the user writes `out[k]` partials;
  (b) allow it with checked int64 partials; any overflow stops loudly, even where the sequential loop would not
      have stopped (a DIFFERENCES entry);
  (c) allow it exactly: each chunk keeps its sum and its highest and lowest prefix in 128-bit ints, so the combine
      step knows whether, and in which chunk, the sequential loop would have stopped. Same result as sequential;
      more code in the PAR runtime.
- **D2. `total += x` on a shared float.** No parallel order equals CPython's left-to-right sum.
  (a) refuse it (as today); (b) allow it only behind an explicit opt-in, with a fixed chunking that is the same for
  every thread count (deterministic, not CPython's last bits); (c) allow it by default with (b)'s order, and a
  DIFFERENCES entry. The ail_array decision of 2026-10-30 chose a fixed sum order there.
- **D3. A parallel body appends to, or otherwise writes, a shared list.**
  (a) as today: the lock-free lowering is refused and the program runs under the lock, with a note;
  (b) a compile error under `--strict`, the note otherwise;
  (c) per-chunk buffers concatenated in iteration order, which equals the sequential result for `map`-like
      shapes (not for free-running `Thread`s, whose CPython order depends on the schedule).
- **D4. A hybrid-mode native call that takes a container while other CPython threads run.**
  (a) keep the GIL for it (this job's default);
  (b) copy the container in before releasing the GIL (parallel, costs memory and a copy per call);
  (c) do not accelerate such a function in a program that imports `threading`.

## Done-check

- Silent races 0 in both builds; every safe probe matches CPython at 1, 2, 4 and 16 threads.
- Safe GIL-free at least today's count plus 2, or a per-probe reason.
- 0 `program.c` hash differences on the 110 thread-free programs.
- The listed tests and the 20 shards pass. D1-D4 are in `RESULTS.md` and in the report.

## Stop rule

Stop and report if closing a race needs `pyfunc.py` or `cruntime.py`, or would turn a program that matched CPython
into a refusal or a stop (a regression under rule 1; falling back to the lock is not a regression). Stop when 80
minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs. Run
   TSan builds one at a time.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `cruntime.py`, `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`.
- `typedpar.py` runs in `ail_syntax.python_surface` before `threadlib.py`; a shape it does not lower goes to
  `threadlib.py` and the general path under the lock, byte for byte as before.
- CPython 3.12 is the oracle: compare stdout and the exit status.

## Owner decisions (2026-11-05, owner said はい to these; they replace "stop and report" for D1-D4)

- **D1** shared int `+=` in a parallel loop: keep refusing it for now (a). Exact semantics (c), which stops where the
  sequential loop stops, are wanted later as their own job. Do not build them here.
- **D2** shared float sum: a fixed chunk order, used only behind an explicit opt-in (b). This matches the typed-array
  decision that sum order is fixed.
- **D3** append to a shared list inside a parallel body: per-chunk buffers joined in iteration order (c). The result must
  equal the sequential one.
- **D4** hybrid native call taking a container while other threads run: keep the GIL (a), the provisional safe default.
Implement D2-D4 only where they fit in this step's 80 minutes. Whatever does not fit, list it as a follow-up job.

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
