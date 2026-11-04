Lane: codegen

**Finish bces2 from its existing work; do not redo it.** The run on branch `job-bces2-11040407` did the work, then ended ERROR because the pipeline's review step crashed (a bug in the job runner, now fixed; not your work's fault), so it got no verdict.

Start by checking whether `origin/integ` already contains this work: if `git diff origin/integ...origin/job-bces2-11040407` adds nothing new, report NOCHANGE and stop.

Otherwise apply that branch's work: cherry-pick, in order, every commit after "export of staging:integ + task" except "agent worker report".

```
git fetch origin job-bces2-11040407
git log --oneline origin/job-bces2-11040407
```

Commits named "worker: uncommitted edits" or "fix: uncommitted edits" hold unfinished work: read them, then finish the job.

Then verify against the original task below: re-run its measurements and targeted tests, check the boundary cases, fix what is wrong, and report the numbers. Time budget: 60 minutes.

**Owner decisions (2026-11-03):** stripped binary growth up to +1% is allowed only on a task whose instructions drop by at least 1%; on every other task the binary must not grow. The recursion-depth limit keeps its current counting (limit 50,000) and the same firing point; do not change how depth is counted.

# bce s2: exact recursion depth in a register for self-recursive IR functions

Repository `https://github.com/J-KAMMA/ail-ci`, branch from `origin/integ` **after bce-s1 merged** (needs
`lab/beatc/bce_census.py`, `AIL_BCE`, `AIL_BCE_AUDIT`, `AIL_CURRENT/test_ail_bce.py`; if any is missing, stop).
Time budget: **80 minutes**. Commit and push after each sub-step (a)–(d); open the PR after (a). Do not touch
`.github/workflows`. Follow Appendix A.

**Number this moves:** tally_lang icount on its perf input drops by at least **5.5%** (hand-edit measured 6.3%:
21.66e9 → 20.29e9). Every other compare-lab task keeps byte-identical C.

## What and why

Today a function in a recursion cycle does `if (++ail_depth > AIL_MAX_RECURSION_DEPTH) ail_die("recursion depth
exceeded");` at entry and `ail_depth--;` before every return (global memory read-modify-write; tally's `ev` runs
329M times). Emitted from `rt ail_depth_enter/leave` (`ir/lower.py` ~lines 532 and 653, `self.recursive`) and
printed at `ir/emit_c.py` ~972–977; `ir/driver.py` ~374 reads `bound.get('recursive')`. The depth count, the trip
point (depth 50,000) and the message must stay **identical**; only where the count lives changes.

## Eligibility (all must hold, else keep today's code)

1. `f` is compiled through the IR, default exception mode (`AIL_IR_EXC` not `checked`), and has no `try`.
2. `f`'s recursion cycle is exactly `{f}` (only self-calls). Find where the call graph marks recursive functions
   (`pyfunc.py`, the whole-program call graph in `to_c`; see SEMANTICS.md §2 "Recursion") and expose the SCC.
3. Every other call in `f` goes to a function that cannot reach any guarded (recursive) function; an unknown
   callee (FFI, callback, function value, hybrid, legacy function whose calls are not in the graph) disqualifies.
4. `f` has no list-return (`__irl`) or exception-entry (`__ir`) variant in play; if it does, skip it (note it).
5. `bce_enabled()` (s1) is true.

## Emission

```c
static int64_t f__d(<params>, int64_t ail_d) {
    if (ail_d > AIL_MAX_RECURSION_DEPTH) ail_die("recursion depth exceeded");
    ... body, self-calls are f__d(<args>, ail_d + 1), no ail_depth-- anywhere ...
}
int64_t f(<params>) { return f__d(<args>, ail_depth + 1); }   /* same symbol/linkage/signature as today */
```

`ail_d` is never assigned after entry (so `setjmp`/`longjmp` cannot clobber it). Other callers keep calling
`f` (GCC inlines the wrapper). Why it is exact: while `f`'s frames are active no other guarded function runs (rule
3) and `f` has no handler (rule 1); a handler below `f` restores the global to the value it saved, which `f`
never changed; callers in other guarded cycles already counted themselves in the global, so `ail_depth + 1` is
the value `++ail_depth` produced before.

**Audit mode** (`AIL_BCE_AUDIT=1`): also keep the old global increment/decrement inside `f__d` and assert
`ail_d == ail_depth` right after the increment (`ail_bce_audit_fail("f", -1)` on mismatch).

## Sub-steps

(a) SCC exposure + eligibility, with `AIL_IR_STATS` lines gaining `"depth": "param"|"global"|"<reason>"`.
(b) Emission + audit variant.
(c) Probes appended to `test_ail_bce.py` `PROBES`. Oracle for depth probes is the **same program built with
    `AIL_BCE=0`** (today's behaviour; CPython's limit is 1000, which AIL already differs from by design); all
    other probes use CPython. Each in default, `AIL_UNIFIED_FORCE=1`, `AIL_BCE_AUDIT=1`:
    - self-recursion to depth 49,999, 50,000, 50,001 (trip message and exit code identical);
    - `f` called from a guarded mutual-recursion pair `g`/`h` at total depth 49,990 + 20 (trip at the same call);
    - `f` raising `ValueError` at depth 30,000, caught in `main`, then `f` called again to 49,000 (no false trip);
    - `f` whose body calls a non-recursive helper (eligible) and one that calls a recursive function (not
      eligible: `AIL_IR_STATS` says why);
    - a tally-like evaluator over parallel lists (`ev(p, i)`), output equal to CPython.
(d) Numbers + DEVLOG entry.

## Done check

- `python3 lab/beatc/bce_census.py check --base /tmp/base --out /tmp/check.json` exits 0: tally_lang/ail icount
  ratio ≤ 0.945, same output; every other task/syntax `same C`. Report tally's stripped bytes (base vs head).
- `tools/par_check.py -j 2 test_ail_bce test_ail_ir_s1 test_ail_ir_s2 test_ail_ir_s3 test_ail_range_checks` and
  the recursion test module (`git ls-files AIL_CURRENT | grep -i recurs`) pass; `tools/codegen_diff.py --pins`
  unchanged (or only recursive pins, listed in the PR).
- Compile time: `tools/compile_phases.py lab/compare/src/tally_lang/main.ail` median of 5, base vs head, within 3%.
- All 20 shards green.

## Stop rule

Stop and report if: any audit run exits 86; the icount drop on tally is below 4% (report the number and the C
of `ev`); the stripped binary of tally grows (report bytes; owner question pending: +1% allowed only when
icount drops ≥1%); eligibility needs changes outside `pyfunc` call-graph code, `ir/lower.py`, `ir/emit_c.py`,
`ir/driver.py`; or 80 minutes pass.

## Appendix A: standing rules (owner-approved 2026-10-30)

1. **No regressions.** A program that built and matched CPython before must still do so after, in the default
   build. A loud stop only where the value cannot be computed. When a fast path cannot handle a case, keep the
   old route.
2. **Big values.** Wherever ints come from text, fields or arithmetic, probe values beyond int64 too. Run every
   probe in the default build AND with `AIL_UNIFIED_FORCE=1` and compare both with CPython.
3. **CI before you report.** Push early, open the PR against `integ` of `J-KAMMA/ail-ci`, wait for all 20
   `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most once every 10 minutes). Report only when all
   pass, or say exactly which fail and why.
4. **Stack at most 2 deep.** Branch from integ or from one unmerged PR, never from a stacked PR.
5. **Memory.** Wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py` at `-j 2` at most; leave no
   background jobs running.
6. Batch `gh` queries; never poll in a tight loop.
7. **Registration.** New test module: add `AIL_CURRENT/tests.d/<module>.txt` containing the module name, `git
   add` it, run `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.
8. **Never** read or print credentials, run a broad `pkill`, merge PRs, change repository settings, cancel runs,
   or edit `.github/workflows`. **No compare-lab number may get worse.**

## Appendix B: measuring on a GitHub runner

`perf_event_open` is denied on runners: `sudo apt-get install -y valgrind`; `lab/beatc/bce_census.py` then uses
callgrind (`--icount auto`). Base tree: `git worktree add /tmp/base origin/integ`. `check` builds both trees,
skips tasks whose C is byte-identical, and fails on any higher icount or changed output. Reference (2026-11-03,
perf counter): tally_lang base 21.66e9; removing all depth bookkeeping 12.3%; this step's register form 6.3%.

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
