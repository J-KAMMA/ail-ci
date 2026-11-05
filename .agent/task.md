Lane: race

# races1: what AIL has for threads today, and a probe suite of racy and safe parallel programs (measure only)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** three counts over a new probe suite `lab/race/`, measured today and written in
`lab/race/RESULTS.md`:
- **silent races**: racy probes that build and then run GIL-free with a shared write, or that print something other
  than CPython, or that ThreadSanitizer flags. The owner's goal is 0: no data race may compile or run silently.
- **safe matched**: safe parallel probes whose output equals CPython's at `AIL_THREADS` 1, 2, 4 and 16.
- **safe GIL-free**: safe probes that run on the lock-free typed parallel path rather than under the general
  path's lock. This is the count later steps raise.
This job changes no compiler file.

What exists (read these first; the design doc that `typedpar.py` names, `docs/design/TYPED_PARALLEL.md`, is not in
the tree):
- `AIL_CURRENT/python/pkg-v12/parallel.py`: `for i in par_range(a, b)` loops. A compile-time ownership proof: the
  body may write only its own locals and `xs[i]`, `xs[i*K + j]`, `xs[i*K + c]`; no append, no I/O, no try, calls
  only to int/float-only functions, no `@extern`. Aliases are stopped at run time before the loop
  (`test_ail_parallel_for`). Scalar reductions (`total += x` on an outer name) are refused.
- `typedpar.py`: lowers `ThreadPoolExecutor(k).map(f, xs)`, `multiprocessing.Pool(k).map(f, xs)` and the
  start-all/join-all `threading.Thread(target=w, args=(k, out))` shape onto `par_range`. Every other shape is left
  to the general path.
- `threadlib.py`, `thread_prelude.py`, `threadrt.py` (stage G12): the general path runs `threading`, `queue` and
  `concurrent.futures` under one interpreter lock with CPython's GIL semantics. Memory-safe, not parallel.
- `ail_ffi.py`: a callback with `threads=True` is refused; a call from another thread aborts.
- `ail_cpython_hybrid.py`, `c_api_bridge.py`, `docs/design/CPYTHON_HYBRID.md`: "every native call releases the
  GIL". A typed function that reads a list while another CPython thread changes it is a race candidate: probe it.
- Tests: `test_ail_parallel_for.py`, `test_ail_typed_parallel.py` (has `test_tsan`, `test_asan_ubsan`),
  `test_ail_threads.py`, `test_ail_ffi_parallel.py`, `test_ail_cpython_hybrid.py`
  (`test_concurrent_overflow_falls_back_per_thread`).

Base: `origin/integ`. Files you may create or edit, and no others:
- `docs/design/TYPED_PARALLEL.md` (new): the current state, one page;
- `lab/race/racy/*.py`, `lab/race/safe/*.py`, `lab/race/hybrid/*.py` (new probes), `lab/race/run.py` (new),
  `lab/race/RESULTS.md` (new);
- `AIL_CURRENT/test_ail_race_probes.py` (new) and `AIL_CURRENT/tests.d/test_ail_race_probes.txt` (new);
- the manifest files that `tools/update_manifest.py` writes.

## Sub-steps

1. **State (15 min).** Write `docs/design/TYPED_PARALLEL.md`: the three mechanisms above, what each accepts, how a
   refusal is reported (note or error), which path a threaded program lands on, how `AIL_THREADS` is read, and
   whether `par_range` can be written in a `.py` program that CPython also runs (find out; if not, say so). Cite
   file and line. Commit, push, open the PR against `integ`.
2. **Probes (35 min).** Ordinary Python 3.12 programs, 10-40 lines, deterministic output on CPython (sort or join
   before printing). At least 14 racy and 12 safe, plus 3 hybrid:
   - racy: workers that write `out[0]`, a neighbour `out[k+1]`, `out[k % 2]`; one list under two names (`a = out`)
     written through one and read through the other at another index; the same list passed twice in `args`;
     `append` to a shared list; `+=` on a global int; a shared dict written; a `map` function that writes a global;
     a nested parallel loop writing the outer list; a thread that resizes a list the others index; a reduction
     `best = max(best, f(k))` on a shared one-element list; a `float` sum into a shared cell; an executor
     `submit` whose task writes a shared list. CPython runs each one; where its result depends on the schedule,
     print only what does not (for example the length), and say so in the file's docstring;
   - safe: `map` of a pure int function and of a pure float function; `Pool.map`; the Thread shape writing
     `out[k]`; blocks `out[k*K + j]`; per-thread partial sums in `out[k]` summed after the join; an exception in
     one worker (the one the sequential loop reaches first must be the one reported); an int result beyond int64
     in a worker (`2**63` from arithmetic: CPython prints it; AIL must print the same or stop loudly); results
     list longer than the worker count; worker count 1; 16 workers on 3 items; a large map (10^6 items);
   - hybrid: build with the CPython hybrid; CPython threads call an accelerated function that reads a list while
     another thread appends to it; one that only takes ints; one that takes a bytearray.
   Commit and push.
3. **Runner and counts (30 min).** `lab/race/run.py` builds each probe in the default build and with
   `AIL_UNIFIED_FORCE=1`, records the path (typed parallel, general with lock, refused) with the note or refusal
   line, runs it at `AIL_THREADS` 1, 2, 4, 16 (3 times each) and compares with `python3`. For builds on the typed
   parallel path it also builds once with ThreadSanitizer the way `test_ail_typed_parallel.test_tsan` does and
   records any report. Write the three counts and a per-probe table in `RESULTS.md` under "Today". Write
   `test_ail_race_probes.py`: it runs the racy probes and asserts none is a silent race, and runs the safe ones and
   asserts they match CPython; mark the probes that fail today as expected failures, by name. Register it
   (Appendix A rule 6). Commit, push, wait for CI.

## Done-check

- `RESULTS.md` has the three counts and one row per probe (at least 29 rows), both builds.
- `docs/design/TYPED_PARALLEL.md` exists and every claim cites a file and line.
- `python3 AIL_CURRENT/test_ail_race_probes.py` passes (today's failures as named expected failures).
- `git diff --stat origin/integ` shows only the files listed above. The 20 shards pass.

## Stop rule

If a probe shows a silent race (wrong output, crash, or a TSan report on a GIL-free build), do not fix it: name it
first in `RESULTS.md` with the exact build command, and report it at the top of your report. Stop when 80 minutes
pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs. TSan
   builds use more memory: run them one at a time.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Edit only the files this task names. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. A fallback to the
  general path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- CPython 3.12 is the oracle: compare stdout and the exit status.
- Owner goal (2026-10-19, `typedpar.py` docstring): typed code drops the GIL and is kept free of data races at
  compile time, with Python's own APIs, so the same program runs on CPython.

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
