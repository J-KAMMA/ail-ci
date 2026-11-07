**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: fbpmap3 (D3 per-block append buffers)

**What the change really does:** `parallel.py` accepts exactly one pre-loop list whose only body use is `out.append(v)` (int/float/`list[str]` literal) in Python-surface and `_ail_par_range` bodies; `pyfunc._par_outline` rewrites the emitted `ail_*_push` into `ail_par_buf_push_*`; `cruntime.PARBUF` adds a mutex-guarded per-block-start buffer table, joined in block order (up to the failing block) before re-raising.

**Verified (my probes, HEAD vs base and CPython/`range` twin):**
- Order/content at 1, 2, 4, 16 threads and `AIL_PAR_SCHED=guided`: `a_int_initial`, `g_multi_full` (2 appends, 600 elems, full order+sum), `h_two_regions`, `i_float_func`, `n_neg_empty`, `q_three_kinds` (int+str+float in one program), `r_bool`, `s_thread_append_order`, `p03`, `p07` — all match.
- Named refusals kept: alias (`e_alias`), bytearray (`j_bytearray`), int/float mix (`k_mixed`), str variable/call (`l_str_var`, `m_str_call`), callee-with-region (`p_callee_region`).
- `test_ail_par_append` + `test_ail_safetynet`: pass. Manifest `--check`: pass.
- C unchanged for no-feature programs: 4 race probes + 14 corpus programs byte-identical.
- TSan: 0 warnings for `map_int`, `p01..p04`, `p07`, `safe/shared_append` at 4 and 16 threads.
- Speed: 2.63x at 4 threads, RSS 1.94x (targets 2x/2x met).
- `lab/race/run.py --quick`: silent races 0, safe matched 17/18, **safe GIL-free 17/18** (base: 16/17). `shared_append` builds typed (no "general path" note, `ail_par_buf_run` present) and prints 10.

**False (committed HEAD):** `lab/race/RESULTS.md` says `safe GIL-free 16 of 18`, marks all 16 typed probes `REPORT: ThreadSanitizer report`, and lists `safe/shared_append.py` as `general`. None of that reproduces.

**Defects**
1. **Committed verification record is false and fails the done-check.**
   Probe: `python3 lab/race/run.py --quick`; `gcc -fsanitize=thread` on the kept C of `lab/race/safe/shared_append.py` at `AIL_THREADS=4,16`.
   Expected (and measured): `safe GIL-free 17 of 18`, 0 TSan warnings, shared_append `typed parallel`.
   Actual in `git show HEAD:lab/race/RESULTS.md`: `16 of 18`, 16 `REPORT` rows, shared_append `general`. The commit message claims "typed path … TSan is clean", so the branch contradicts itself. A corrected copy exists only as an **uncommitted** edit (appeared at 01:28:48, not made by me); `run.py` also rewrites this file.
2. **Required probe missing: "an exception halfway with a `try` that prints `out`".** `p04_exception.py` has no `try`, so the partial-buffer join is never observed. A `try` around the loop is refused on *both* HEAD and base (`parallel for cannot be inside try`), so the claim "`out` holds exactly the state the sequential loop leaves" is untested/unobservable.

**Code observation (not demonstrated as wrong output, item 4b):** `_par_outline`'s `pb` early return precedes the `facts['cap']` return, so an append region that also carries a worker cap runs `ail_par_buf_run` (unbounded `ail_par_threads()`) instead of `ail_par_run_n`. Ordering/output is unaffected; only the `workers` contract is dropped.

**Pre-existing:** `par_range` inside `try` refused (both trees); `par_range` unknown on the forced general path (both); alias/second-name refusal (both).

**Not checked:** `test_ail_files`, `test_ail_corpus_findings3`, the 20 CI shards, the full 110-program hash list (sampled 18 programs), and the exception-join runtime path (unobservable).

VERDICT: FIX
1. Commit the corrected `lab/race/RESULTS.md` (17/18 GIL-free, TSan clean, `safe/shared_append.py` = typed parallel); the committed table currently records the opposite.
2. Add the required exception-in-`try` probe (or record and assert the refusal by name) so the partial-buffer join is actually exercised.
[commandcode stop=end_turn turns=43 out_tokens=60925]


--- ORIGINAL TASK ---
Lane: fb-pmap
Needs: fbpmap2 fbred3

# fbpmap3: `out.append(v)` in a parallel body through per-chunk buffers joined in iteration order (D3 option c)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

First check `lab/race/RESULTS.md` on `origin/integ`: if races2 already landed D3, report NOCHANGE and stop.

**Number this moves:** the three counts of `lab/race/run.py`. Targets: silent races 0; safe GIL-free up by at least the
new append probes; racy `shared_append.py` (a map-like shape) runs on the typed parallel path and prints the sequential
result. Also the 4-thread speedup of an append variant of `par_collatz` (keep `n` whose step count is odd): at least 2x,
with peak RSS at most 2x the sequential build's.

**The rule.** In a map-like parallel body (`par_range`, the `_ail_pmap` loop, `Pool.map`; not a free-running `Thread`
list, whose CPython order depends on the schedule), a list `out` defined before the loop whose only use in the body is
`out.append(v)` (any number of times per iteration, conditional or not), with `v` an int, float or str. Each block
appends into its own buffer of the same element kind, in its own iteration order. After the region, the buffers are
appended to `out` in block-index order, which equals the sequential order because blocks are contiguous. If an
iteration raises, `out` gets the buffers of every block before it plus the failing block's buffer up to the raise, and
nothing after: the state the sequential loop leaves. Str buffers own their references and move them into `out` without
an extra retain. Lists of objects, and any other use of `out` in the body, keep today's refusal.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/parallel.py`, `AIL_CURRENT/python/pkg-v12/typedpar.py`;
- `AIL_CURRENT/python/pkg-v12/pyfunc.py`: `_par_for`/`_par_outline` only, at most 40 lines (rebase on `origin/integ` just
  before each push); `cruntime.py`: a new part `PARBUF` only;
- `lab/race/append/*.py` (new probes, at least 8: conditional append, two appends per iteration, str appends, an
  exception halfway with a `try` that prints `out`, an empty range, more workers than items, 16 threads, the guided
  schedule), `lab/race/append/RESULTS.md` (new), `docs/design/TYPED_PARALLEL.md`;
- `AIL_CURRENT/test_ail_par_append.py` (new), `AIL_CURRENT/tests.d/test_ail_par_append.txt` (new);
- the manifest files that `tools/update_manifest.py` writes.

## Sub-steps

1. **Probes and the shape (25 min).** Probes first, compared with CPython; then `parallel.py` accepts the shape.
   Commit, push, open the PR against `integ`.
2. **Buffers (20 min).** `PARBUF` and the hook. Every probe matches at 1, 2, 4 and 16 threads, three runs each, with
   `AIL_PAR_SCHED` set and unset. Commit and push.
3. **Verify (15 min).** `lab/race/run.py` both builds; the `program.c` hash of the 10 compare tasks and the first 100
   `lab/corpus/programs` unchanged; the speed and RSS numbers; TSan. Commit, push, wait for CI.

## Done-check

- Every append probe matches CPython at every thread count; silent races 0; safe GIL-free up.
- 0 hash differences on the 110 programs; TSan clean; the 20 shards pass.

## Stop rule

Stop on any wrong output or TSan report. Record it first. Stop if the hook needs more than 40 `pyfunc.py` lines: write
the change into `RESULTS.md` and stop. Stop when 60 minutes pass. Push what is done first.

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

## Owner decision (2026-11-06)

- During the D3 join, peak RSS may reach up to 2x the output size.

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
