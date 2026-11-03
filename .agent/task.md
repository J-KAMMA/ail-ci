Lane: frontend

**Finish rails3 from its existing work; do not redo it.** The first run (branch `job-rails3-11040144`) did the work, then ended ERROR (a review that gave no answer or hit a model limit), so it got no verdict.

Start by checking whether `origin/integ` already contains this work (a later job may have carried it): if `git diff origin/integ...origin/job-rails3-11040144` adds nothing new, report NOCHANGE and stop.

Otherwise apply that branch's work: cherry-pick, in order, every commit after "export of staging:integ + task" except "agent worker report".

```
git fetch origin job-rails3-11040144
git log --oneline origin/job-rails3-11040144
```

Commits named "worker: uncommitted edits" or "fix: uncommitted edits" hold unfinished work: read them, then finish the job.

Then verify against the original task below: re-run its measurements and targeted tests, check the boundary cases, fix what is wrong, and report the numbers. Time budget: 60 minutes.

# rail-s3: a `range(a[s], a[s + 1])` counter must stay int64, not a tagged `ail_tint`

Background: `rail-design.md` (appendix below)
(section "secondary codegen issue"). This step is independent of rail-s1 and rail-s2. Branch from `origin/integ`.

**Number it moves:** instructions of t3.ail mode 0 (below), from **181.7 M to 105 M or less**. That is the level of
mode 1, where the bounds are hoisted: 101.8 M. The loop runs 20 M CSR iterations, so this is about 4 instructions per
iteration. On rail_transfer after rail-s1 it is worth less than 1%. The value is general: every CSR or adjacency loop
whose bounds are list elements, in any function that is not `main`.

## Symptom

In the default typed build, this function

    fn fd(a: list[int], b: list[int], s: int) -> int {
        let t = 0;
        for j in range(a[s], a[s + 1]) { t += b[j]; }
        return t;
    }

emits `ail_tint v_j` and `ail_tint_from_int64` / `ail_tint_i64` on every iteration. The same loop written as
`let lo = a[s]; let hi = a[s + 1]; for j in range(lo, hi)` emits a plain int64 (0 ail_tint). A constant stop does too.
rail_transfer's `solve()` shows the same thing for `v_n` and `v_e`.

t3.ail (also at `the design session's scratch dir (not available here; regenerate with the task's gen.py) t3.ail`; it reads the mode from stdin, 0 = fd, 1 = fe):

    fn fd(a: list[int], b: list[int], s: int) -> int {
        let t = 0;
        for j in range(a[s], a[s + 1]) { t += b[j]; }
        return t;
    }
    fn fe(a: list[int], b: list[int], s: int) -> int {
        let t = 0;
        let lo = a[s];
        let hi = a[s + 1];
        for j in range(lo, hi) { t += b[j]; }
        return t;
    }
    fn main() {
        let mode = int(input());
        let n = 1000;
        let a: list[int] = [];
        for i in range(n + 1) { a.append(i * 1000); }
        let b = [1] * (n * 1000);
        let t = 0;
        for r in range(20) {
            for s in range(n) {
                if mode == 0 { t += fd(a, b, s); } else { t += fe(a, b, s); }
            }
        }
        print(t);
    }

## Cause (start here)

`AIL_CURRENT/python/pkg-v12/bigcap.py`:
- `_lp_range_value`: if any argument has no bounds (a Subscript evaluates to an unbounded value) and the start is not
  bounded, it returns None.
- The `ast.For` branch of `_lp_run` (around line 1214): `iv = _lp_int()`, an int with no bounds.
- `proven_int_names` then leaves `j` unproven, and `pyfunc.py` (around line 36015, `_bounds`/`_proven`/`_unproven`)
  tags it.

The fix: a range counter always lies between its start and its stop. When every range argument is a value whose C
storage is int64, the counter is int64 too. That holds for an element of an int64 `list[int]`, an int field, or an int
local or parameter that is not itself tagged. So give the counter the int64 bounds
`[_LP_I64_MIN, _LP_I64_MAX]` instead of no bounds. Arithmetic on the counter (`g.ns + j`) stays checked (`ck_add`) as
now.

Do NOT apply this when an argument may be a tagged or big value: `--exact-int` / `AIL_EXACT_INT`, a tagged parameter,
or a general-path value. In that case keep today's route.

## Sub-steps (commit and push after each one)

1. Add the rule in bigcap.py. Check that `fd` above emits no `ail_tint` and that `fd` and `fe` give the same output.
   Get the C with `compile --strict --no-cache t3.ail -o /tmp/t3 --debug-dir /tmp/t3dbg`, run icount on modes 0 and 1,
   and put both numbers in the commit message. Commit and push.
2. Tests. Add cases to `AIL_CURRENT/test_ail_tint.py` or to a new module registered in `tests.d`. Run
   `tools/update_manifest.py`, then `--check`. Compare each with CPython:
   - a list-element bound, a struct-field list bound, a negative step, an empty range, and bounds of
     ±9223372036854775807
   - a counter used in `j * j` that overflows (a loud stop, the same as today)
   - the same programs under `--exact-int` with list elements above 2**64, which must stay exact

   Run each in the default build and with `AIL_UNIFIED_FORCE=1`. Also run `test_ail_tint.py`,
   `test_ail_int64_default.py`, `test_ail_int64_edges.py`, `test_ail_range_checks.py`, `test_ail_bigcap_split.py` and
   `test_ail_optint_exact.py`. Commit and push.
3. Census. Count how many generated functions lose `ail_tint` with this rule, over the lab/compare `.ail` sources and
   the lab/corpus programs that build typed: grep `ail_tint_from_int64(` in the `--debug-dir` C, before and after. Put
   the count in the PR. Then `tools/par_check.py -j 2` under `ulimit -v 1500000`, then the PR and all 20 shards.

## Stop rules

- If the rule needs changes outside bigcap.py and the one `pyfunc.py` call site, stop and report. That would be a
  larger design.
- Any program that built and matched CPython before must still do so. If one now refuses or differs, revert and
  report the program.
- If t3 mode 0 does not reach 105 M or less, report the generated loop and stop.


## Appendix (files from the design session, copied here because the runner cannot read them)

### rail-design.md

````
# rail_transfer: why AIL takes 862 ms against Rust's 48 ms (diagnosis, 2026-11-02)

Base: ail-ci `origin/integ` 4f1245b1, worktree `/home/bluec/pub/wt-rail-diag`. Measurements were taken on the laptop
(WSL). Instruction counts come from `tools/icount.c` (perf_event); they are deterministic. The working files are in
`/home/bluec/pub/rail-diag-work/` (WSL): perf.in, q0.in, the case*.in files, uni.c, p0-p3.ail, t3.ail and the generated
C in dbg/program.c.

## Verdict

**This is a benchmark bug, not a compiler bug.** `lab/compare/src/rail_transfer/main.ail` runs a **one-sided** Dijkstra
per query and stops only when it pops the target. `main.c`, `main.rs` and `main.go` all run a **two-sided**
(bidirectional) Dijkstra with a meet-in-the-middle stop. On the perf input the AIL program pops **128x more heap
entries** than the C program. A hand-written C port of the AIL algorithm is as slow as AIL. No compiler or runtime change
can close the gap: the compiler-only bound is about 13% of instructions.

## Profile (perf input: N=100000, M=180389, Q=25; output md5 e04679834cdf3d4d8441f9adf3182e91 for all builds)

| build | instructions | of which Q=0 (parse + graph) | query phase | heap pops | wall (quiet laptop) |
|---|---|---|---|---|---|
| Rust main.rs | 236 M | 214 M | 22 M | (bidir) | 0.04-0.08 s |
| C main.c | 281 M | 267 M | 14 M | 29,243 | 0.07-0.16 s |
| AIL main.ail (typed) | **2,892 M** | 327 M | **2,565 M** | **3,746,078** | 0.82-1.47 s |
| hand C port of main.ail (uni.c) | 2,505 M | 68 M | 2,437 M | same as AIL | 0.77-0.92 s |

- Query phase share of AIL: 88.7% of instructions and about 95% of wall time.
- In the query phase AIL costs 2,565 M against 2,437 M for hand C on the same algorithm, so the code AIL generates is
  only 5% worse. The heap is already a record heap (`ail_rl_III`, `ail_rh_pop_III_0_1_2`): no boxing, and no
  allocation per push.
- The gprof hot list for the generated C is solve (53%), ail_rh_down (33%), push (3%) and input/parse (the rest). These
  are the costs of the algorithm, not of a pathology in the runtime.

## Pricing (speed-claims)

**Fix A: port the two-sided search into main.ail (step S1).**
- Measured share: the query phase is 2,565 M of 2,892 M (88.7%). The Amdahl bound is 2,892/327 = 8.8x on
  instructions.
- Expected after the fix: setup 327 M (measured with Q=0) plus a query phase of at most 2x C's 14 M, so about
  **330-360 M instructions (1.4-1.5x Rust's 236 M)**.
- Expected wall time on CI: the AIL Q=0 run costs about the same as the full Rust run on the laptop (1.0-1.5x across
  quiet and noisy runs). That gives **about 50-75 ms against Rust's 48 ms, down from 862 ms** (an 11-17x gain).
- If the fix lands short of this, a stop rule applies (see S1).

**Fix B: a compiler-only change on the current source.** It is rejected as the fix for this task. Even perfect C for
the same algorithm is 2,505 M instructions and about 0.8 s. The best case is -13% of instructions (862 → about 750 ms),
which is still more than 15x Rust.

**After S1 the remaining gap is the stdin parse, which is general (step S2).** Microprograms run on q0.in
(180,389 lines of 4 ints, about 22 bytes each). Each figure below is the cost added by one more piece:

| piece | instructions per line |
|---|---|
| `let f = input()` | 453 |
| `.split()` | 350 |
| 4 x `int(f[k])` (including slist_get) | 345 (86 per field) |
| **total** | **about 1,150 per line = 207 M** |

Hand C parses a whole line in about 120 instructions. After S1 the parse is 59% of AIL's instructions. Cutting it to
500 per line or less saves at least 117 M, so AIL would come to about 230 M, level with Rust's 236 M. The same
`input().split()` + `int()` shape appears in 30 of the lab/corpus programs and in most stdin tasks.

**A secondary codegen issue that is general (step S3).** `for j in range(a[s], a[s + 1])` (a list element as a bound)
makes `j` a tagged `ail_tint` in the typed int64 build. Every iteration then pays ail_tint_from_int64 →
ail_tint_add_i64/ail_tint_i64. With the bounds hoisted (`let lo = a[s]; let hi = a[s + 1]; for j in range(lo, hi)`)
`j` is a plain int64. The micro t3.ail does 20 M iterations of a CSR loop: 182 M instructions as written, 102 M with
the bounds hoisted (-44%). The same pattern is behind rail_transfer's `v_n` and `v_e`. On rail_transfer after S1 it is
worth less than 1%. The value is in every CSR or adjacency loop in other programs. The cause is in
`python/pkg-v12/bigcap.py` `_lp_range_value`/`local_int_bounds`: when the range start is a Subscript with no bound, the
counter gets `_lp_int()` with no bounds. The rule and the price are in S3.

## Same pathology elsewhere

- The other 9 lab/compare tasks are within 0.8-2x of the best language. None shows a 10x outlier, so none has a
  divergence of this kind. Only `rail_transfer/main.ail` uses `heappush(..., key=lambda)`.
- `rail_transfer/main.py` is also one-sided: it groups queries by source and runs one search per source without
  stopping early. It is not part of this fix. It feeds the CPython column and the `ail-py` column, so the `ail-py`
  column will keep the slow algorithm. Note this in the README; whether to change main.py is the owner's call, because
  it changes the CPython baseline.
- `main.nim` groups queries by source and checks connectivity with union-find. Go is two-sided and multi-threaded.

## Provenance caveat (for the owner)

The lab/compare sources are the LLM-written programs from llm-compare round 4. S1 replaces an LLM-written AIL program
with a hand port of the C algorithm. That is the right comparison for language and compiler speed (same algorithm). It
does change what the AIL column means for "LLM-written code", so the README must say so (S1 does this).

## Correctness gate (every step)

1. Run `lab/compare/run_task.py --task rail_transfer --langs ail,c,rust` on the laptop (the perf input is 4 MB, RSS
   under 40 MB). It must report every public and hidden case equal to reference.py, `path` must be `typed`, and the
   perf stdout must be identical (md5 e04679834cdf3d4d8441f9adf3182e91).
2. Differential fuzz against `tasks/rail_transfer/reference.py`: at least 300 `random_net` cases from `gen.py` with
   varied n, line counts, maxx=0, maxt=0, T=100000 and X=1000. Build both default and `AIL_UNIFIED_FORCE=1` (without
   `--strict`). Outputs must be byte-identical.
3. Full suite once per merge batch: `tools/par_check.py` at `-j 2` at most, under `ulimit -v 1500000`. Then all 20 CI
   shards on the PR (agent-brief-rules 3).
4. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`: no regressions, probe big values, memory cap, and a stack at
   most 2 deep.

## Stop rules

- S1: if `compile --strict` refuses the port (general path), or the AIL instructions on perf.in come out above 500 M,
  stop and report the refusal or the profile. Do not tune further in the benchmark source.
- S2/S3: each must move its named number by the stated amount without changing any output. If the first measured
  sub-step cannot reach the number, stop and report the breakdown. Do not stack speculative changes.
- Any output difference against reference.py or CPython, in any mode: revert and report the case.
- Do not declare a win from laptop wall time. Instructions are the laptop metric. CI compare-lab (run manually by the
  integrator) gives the real ms.

````

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
