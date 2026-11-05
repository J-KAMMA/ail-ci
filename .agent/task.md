**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review — recstop1 (job-recstop1-11060031)

**What the change really does**
- General path: every generated function entry (`pyboxed2` top-level functions and methods, `boxclosure` nested defs) now compares its frame address with `cx->stack_limit` and raises `RecursionError("maximum recursion depth exceeded")` through the normal exception path. The limit is derived from `RLIMIT_STACK` in `ail_ctx_init`, `pthread_getattr_np` for threads, and the generator's own mmap; the first-cut 10000-frame counter is removed (a 10000-level `yield from` counter was added instead).
- `RecursionError` becomes a real builtin class (base RuntimeError); the typed path's `ail_die` recursion trap is mapped to `AIL_EXC_RUNTIME` so `except RuntimeError` catches it, with its name overridden on the uncaught print.
- Records: DEVLOG, DIFFERENCES (2 rows), `docs/LIMITATIONS.md`, `lab/safety/stops/`, new `test_ail_recursion_stop.py`.

**Verified claims**
- 06/07/08 stop by name, 0 crashes: re-ran the safety table at HEAD (`run.py` with only the output path redirected): **match 66, stop-differs 10, documented difference 3, refused 1, crash 0, silent-wrong 0** — exactly the report's counts. On `work`, 06 general still exits 139 with `prefix 10` lost (the defect being fixed).
- Deep direct recursion: uncaught general/default → exit 1, last stderr line `RecursionError: maximum recursion depth exceeded`, stdout preserved (p3). Depth 5000/12000 complete; 5000/12000 are documented differences (p4, p19).
- Routes: argument, list item, dict value, attribute, closure, `*args`, `__call__`, method, threads, `yield from`, small stacks (`ulimit -s 64/128/256`); 60-locals recursion now stops by name where base segfaults.
- 4b (I/O): read-then-overwrite, bytearray slice+mutate, list slice+mutate match CPython (p18_io); the `filert` flush edit is equivalent.
- Non-recursive program: `--debug-dir` C vs `work` differs only by the new runtime/guard additions, no codegen shuffling; output unchanged.
- Test modules: `test_ail_recursion_stop`, `test_ail_safetynet` → **2 modules, 0 failed** (`-j 2`).

**Defects (new, caused by the change)**
1. A *caught* recursion stop on the typed/default path is a `RuntimeError` instance, not `RecursionError`. Probe `p23_typed_typename.py` (`rec(n:int)->int` recursing, `except RuntimeError as e: print(type(e).__name__)`): CPython/general → `RecursionError`; default build → `RuntimeError`. `p12_exc_attrs.py` likewise prints `RuntimeError` / `True` vs CPython `RecursionError` / `True`. Cause: `ail_exc_kind_of` maps the message to `AIL_EXC_RUNTIME` (code 7) and `EXC_NAMES['RecursionError']=7` aliases the typed handler to RuntimeError, so the class object is RuntimeError (and typed `except RecursionError` would over-catch plain RuntimeErrors). Base refused `except RecursionError` by name, so this is newly reachable wrong output. The new tests only assert a printed string, not the class.
2. Artificial generator depth cap lowers working recursion: `p22_gen12000.py` (`yield from` chain depth 12000) — base general: exit 0, prints `1`; HEAD general: exit 1, `RecursionError: maximum recursion depth exceeded`. `AIL_MAX_GENERATOR_DEPTH=10000` changes how deep recursion may go, which the task forbids (each generator has its own 8 MiB stack; no real exhaustion).
3. Hard-coded 8 MiB fallback when `RLIMIT_STACK` is unlimited: `p17b.py` (`f(300000)`, general build) under `ulimit -s unlimited` — base: exit 0, prints `300000`; HEAD: exit 1, `RecursionError`. `ail_stack_limit_from` falls back to 8 MiB for `RLIM_INFINITY`, so the DIFFERENCES claim "there is no frame cap, so any depth that fits the real stack keeps working" is false there.

**Report accuracy**: counts and most behaviours verified; "6 tests" is wrong (8 in `test_ail_recursion_stop.py`); "cost unchanged / icount" cannot be checked here (`perf_event_open: Permission denied`, confirmed), so the ≤0.5 % budget is unverified; the caught-type defect contradicts "catchable like CPython's". `RESULTS.md` records base `f4cdda42` rather than the final commit (I regenerated an identical table at HEAD).

**Pre-existing** (identical on `work`): typed/default `stop-differs` rows 04, 12, 16, 17, 18; `19_stop_iteration` typed refused; general-path recursion SIGSEGV itself.

**Unverified**: instruction-count cost (hardware counter unavailable); a frame larger than the 64 KiB `AIL_STACK_MARGIN` (compiling a 10000-local function did not finish within 400 s; the prologue could pass the guard with such a frame); typed-path `except RecursionError` over-catching a plain RuntimeError (typed programs that `raise` fall back to the general path, so no probe reached it).

VERDICT: FIX
1. Typed/default caught recursion trap has the wrong class: `p23_typed_typename.py` / `p12_exc_attrs.py` — expected `RecursionError`, actual `RuntimeError` (uncaught name and stdout are right).
2. `yield from` depth 12000 no longer works: `p22_gen12000.py` — base exit 0 prints `1`, HEAD exit 1 `RecursionError` (`AIL_MAX_GENERATOR_DEPTH`).
3. General path is capped at 8 MiB when the stack is unlimited: `p17b.py` under `ulimit -s unlimited` — base exit 0 prints `300000`, HEAD exit 1 `RecursionError`.
[commandcode stop=end_turn turns=55 out_tokens=36100]


--- ORIGINAL TASK ---
Lane: rterrfix

# recstop1: deep recursion must stop loudly, never with a bare SIGSEGV (safety hole found by safestop1)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap). Stop on any wrong output against CPython.

**Number this moves:** `lab/safety/stops/RESULTS.md` (from job safestop1, branch `job-safestop1-*`; cherry-pick its
files if they are not on integ yet). Today `06_rec_direct.py`, `07_rec_mutual.py` and `08_rec_method.py` crash on the
**general** path with signal 11 and nothing on stderr. The target: all three exit nonzero, and the last stderr line
starts with `RecursionError:`, in every mode.

Owner rule: AIL matches CPython or stops loudly by name; it never dies silently. A segfault prints nothing, so it
breaks the 0.1 safety claim.

Do **not** change how deep recursion may go. `09_rec_deep5000.py` (depth 5000, which CPython refuses at its default
limit 1000, while AIL completes) is a separate owner decision. Leave it as is and keep its row in RESULTS.md.

## Steps

1. **Reproduce (10 min).** Build the three programs with `AIL_UNIFIED_FORCE=1` (the general path) and in default mode.
   Record the exit signal. Find why the typed path already raises `RecursionError` (a depth counter or a stack check
   in the typed emitter or runtime) and why the general path lacks it.
2. **Fix (50 min).** Give the general path the same check the typed path uses, so `RecursionError` is raised from
   AIL's own exception path, catchable like CPython's. If that cannot fit, install a last-resort guard: a
   `sigaltstack` and `SIGSEGV` handler that tells a stack overflow (fault address near the stack guard) from other
   faults. On a stack overflow it prints `RecursionError: maximum recursion depth exceeded (stack overflow)` and
   exits 1; on any other fault it re-raises the signal. Keep the cost small: run icount on 3 compare-lab programs
   (tools/icount.c), with no regression over 0.5%.
3. **Verify (20 min).**
   - Rerun the safestop suite: 06, 07 and 08 must show `match` or `stop-differs` (a loud stop), with 0 crashes.
   - The other modes and rows must be unchanged.
   - Run the test modules of the files you touched.
   - Run `python3 -m compileall -q -j 0 AIL_CURRENT tools`.
   Report the counts before and after, and the icount ratios.

## Owner decision (2026-11-05)

- Deep recursion within the real stack (e.g. depth 5000) keeps working: AIL does NOT emulate CPython's default recursion limit of 1000. Record this as a documented difference (DIFFERENCES.md and docs/LIMITATIONS.md), and classify `09_rec_deep5000.py` in RESULTS.md as "documented difference", not silent-wrong. Only a real stack exhaustion must stop loudly with RecursionError.

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
