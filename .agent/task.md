**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: fbnarrow3 (`AIL_NARROW_INT=1` → `ail_ilist`)

**What the change really does.** Adds `ir/narrowint.py` (runtime + `_Generic` op macros + a per-function local analysis and a per-program field analysis) and 61 lines in `pyfunc.py` that store chosen `list[int]` locals and class fields as an int32 buffer, widening to an int64 buffer at run time; with the variable unset `enabled()` is false everywhere and the emitted C is unchanged.

**Probes** (`/tmp/rprobes`, own runner = CPython vs default vs `AIL_NARROW_INT=1`; `cmp.sh` equivalent; base = `/tmp/base` from `work`).

| probe | covers | HEAD default vs CPython | narrow vs CPython |
|---|---|---|---|
| p01 local append/index/aug/pop/del/clear in a method | narrowed local ops | same | same |
| p02 field→local, local→field, field→field, alias kept | ownership | same (pre-existing) | same |
| p03 append/clear during `for in` | mutation in iteration | differs (pre-existing) | same as its base |
| p04 field copy/pop/reverse/while/`=[]`/`=[1,2,3]` | field ops | same | same |
| p05 `append(1.5)` into `list[int]` | type boundary | same | same |
| p06 int32/int64 bounds via local | widths | same | same |
| p07 `t.w.sort()` at module level | blocked op in entry | same | same (field not narrowed) |
| p08 `del`/slice on field | blocked ops | same | same |
| p09 lambda over local/field | blocked capture | same | same |
| p10 `w[i] += v`, `w[-1] -= v` | augmented index | same | same |
| p11 field widened by `=`/`append`, then read/reverse/pop | wide field | same | same |
| p12 values via param, dict value, field element | value sources | same | same |
| p13 subclass method over inherited field | inheritance | same | same |
| p14 ctor local stored into field | ctor path | same | same |
| p15 wide local reverse/del/clear/for | wide local | same | same |
| p16 set-overflow, clear+append, self/store copy, error texts | edges | same | same |
| **p19 try + `for v in xs`** | exc-frame locals | **same** | **BUILD FAILS** |

Default-build C identity: p02/p04/p11/p15 `program.c` byte-identical HEAD vs `/tmp/base` (`--debug-dir`, `AIL_NO_CACHE=1`, `PYTHONHASHSEED=0`).

**Tests.** `test_ail_narrow_int.py` 9/9 OK; `test_ail_safetynet.py` 5/5 OK (run directly — `par_check.py` cannot start, see defect 2).

### Defects
1. **Invalid C when a narrowed local is also a `try`-frame cell.** In `_one_function_numeric_impl` the frame-cell declaration still hardcodes `'ail_list' if t == LIST` (`pyfunc.py:42863`); the narrow declaration was only added to the plain-automatic branch (`:42892`). Any function that owns a `try` and mentions the local in it keeps the cell as `ail_list`, while `_iter_plan`/`_for_inner_impl` emit the non-macro call `ail_ilist_get(&local, i)` on it.
   Probe `/tmp/rprobes/p19_try_for.py` (class with field `w`, `xs=[]`, `w.append`, `try: xs.append(5)`, then `for v in xs`): default build prints `5\n1 1` = CPython; with `AIL_NARROW_INT=1` the build ends `exit 4` — `the C compiler rejected this: ... ail_ilist_get from incompatible pointer type [-Werror=incompatible-pointer-types] ... ail_list *`. If the build did not use `-Werror`, the 24-byte `ail_list` cell would be read through the 40-byte `ail_ilist` layout (silent wrong values), so this is not just a diagnostic.
2. **Manifest is stale on HEAD.** `python3 tools/update_manifest.py --check` → `stale python/pkg-v12/ir/narrowint.py`; `tools/par_check.py -j 2 test_ail_narrow_int test_ail_safetynet` aborts with `ValueError: hash mismatch: python/pkg-v12/ir/narrowint.py`. The recorded hash matches commit `76efe810`; commit `6ea45c48` edited `narrowint.py` afterwards without re-running `update_manifest.py`. CI preflight will fail on this branch.
3. **The instruction-count target is missed.** The task: tree_fold's run instructions "not worse by more than 1%". The worker's own number (also measured in the previous review) is 954.2M Ir vs 856.9M default = **+11.35%**, driven by the per-access `p` test and the int32 range test on push/set. The remedy in the brief (drop the operation / leave the list int64) was not applied; `NARROW_RESULTS.md` only documents the miss.

### Pre-existing (identical on base, not blocking)
- Iterating a list field while appending to it visits different elements than CPython (p03; identical on `/tmp/base`).
- `pop` error texts: AIL prints `list index out of range` for `pop(9)` / empty `pop()` where CPython says `pop index out of range` / `pop from empty list` (p16, identical on base).
- `ys = self.w` copies rather than aliases (p02), and the resulting `IndexError` text differs identically on base.

### Claims vs observation
1. "61 lines in `pyfunc.py`" — verified (`git diff --stat`: 61).
2. "peak RSS 332,100 vs 367,216 KiB (−9.57%)" — unverified by me; direction is consistent with review 0.
3. "+11.35% Ir over default" — verified (worker's own figure, plus review 0's independent measurement).
4. "10 tasks, 511 cases, 0 differences" — unverified (only my own programs checked).
5. "108/110 `program.c` identical without the variable" — partially verified: 4/4 list-heavy probes byte-identical; base behaves as described elsewhere.
6. "manifest updated, `--check` clean" — **false** (defect 2).
7. "or a pass to a list that is itself narrowed" / "fixpoint over the call graph" — **false**: `_local_use_ok` returns False for any call argument, parameters are excluded by `name in ctx.kind`, and the analysis is intra-function; there is no call-graph fixpoint (p01's callee argument never narrows). Conservative, but not what the doc says.
8. "only field-touching functions leave IR" — verified in code (`narrowint.blocks_ir`) and in the C (`v_xs` is `ail_list` in an IR-stayed function).
9. "Tests: 9/9 OK; safetynet passes" — verified.

### Unverified
The 511-case matrix on the other nine tasks, their per-task RSS/instruction numbers, the fbnarrow1 emulated comparison, `test_ail_files`/`test_ail_corpus_findings3` (blocked by the stale manifest), and a `--library` build with the variable set (the `prepare([], classes, …)` early path marks every list field narrow with no function scan).

VERDICT: FIX
1. Narrowed local + `try` frame cell emits invalid C. Probe `/tmp/rprobes/p19_try_for.py`; expected `5` then `1 1` (CPython and the default build agree), actual `AIL_NARROW_INT=1` build exits 4 with `ail_ilist_get ... from incompatible pointer type` at `v_v = ail_ilist_get(&(*v_xs), v__k2)`; fix the frame-cell type at `pyfunc.py:42863` to use the narrowed type.
2. Manifest stale for `python/pkg-v12/ir/narrowint.py` on HEAD (`update_manifest.py --check` reports stale; `par_check.py` aborts with `hash mismatch`); re-run `tools/update_manifest.py` after the final edit.
3. tree_fold instructions are +11.35% over the default build against a ≤1% requirement; keep the offending lists `ail_list` or drop the per-call widening test, per the brief's stop rule.
[commandcode stop=end_turn turns=56 out_tokens=66089]


--- ORIGINAL TASK ---
Lane: fb-narrow

# fbnarrow3: the typed path stores `list[int]` locals and fields as `ail_ilist` where every use is supported (opt-in `AIL_NARROW_INT=1`)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** tree_fold peak RSS with `AIL_NARROW_INT=1` against the default build. Target: within 3% of
fbnarrow1's emulated value (`lab/mem/NARROW.md`), with tree_fold's run instructions not worse by more than 1%. With the
variable set, the 10 compare tasks print exactly what they printed before, and none is worse by more than 0.3% in run
instructions or 1% in peak RSS. Without it, `program.c` is byte-identical to the base on the 10 tasks and the first 100
`lab/corpus/programs`.

**The rule.** A `list[int]` local, parameter, return value or class field becomes `ail_ilist` only when every use of it
is in this set: `.append(v)`, `len(x)`, index read and write with an int index (negative indexes as today), `for v in x`,
`x.pop()`, `x.clear()`, a whole store into a field or local of the same kind, and passing to a parameter that is itself
chosen as `ail_ilist`. Choose by a fixpoint over the call graph and over every function that touches a class field,
starting from "all narrow" and demoting. Any other use keeps `ail_list`: slicing, `+`, `*`, `in`, `index`, `count`,
`sort` with a key, a second name for the same list, storing into another container, a builtin that expects `ail_list`,
FFI, the hybrid boundary, a parallel body. fbnarrow4 adds slices, copies and sorts.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/ir/narrowint.py` (new): the analysis and the operation table;
- `AIL_CURRENT/python/pkg-v12/pyfunc.py`: the kind-selection hook next to arena1s4's packed `ail_pslist` local
  selection, and the list-operation emitters' dispatch on the new kind; at most 120 changed lines in total, listed in
  `lab/mem/NARROW_RESULTS.md`. `pyfunc.py` is busy (codegen, pyreach): rebase on `origin/integ` just before each push;
- `AIL_CURRENT/test_ail_narrow_int.py` (new), `AIL_CURRENT/tests.d/test_ail_narrow_int.txt` (new);
- `lab/mem/NARROW_RESULTS.md` (new);
- the manifest files that `tools/update_manifest.py` writes.

## Sub-steps

1. **Tests first, then the analysis (20 min).** Write the tests: values 2147483647, 2147483648, -2147483648,
   -2147483649, the int64 limits, a stop beyond int64 with the same OverflowError text as today, a field list widened
   in one function and read in another, negative indexes, the IndexError texts, a list passed through two calls, an
   empty list. Each one is compared with `python3` with the variable unset and set, and with `AIL_UNIFIED_FORCE=1`.
   Write `ir/narrowint.py` and print the chosen lists for tree_fold under `--debug-dir`. Commit, push, open the PR.
2. **Emit (25 min).** The hook and the operation dispatch. Build tree_fold and the 10 tasks with the variable set and
   check the output on every public and hidden case. Commit and push.
3. **Measure (15 min).** The numbers above, plus the hash check without the variable. Fill `NARROW_RESULTS.md`: which
   lists became narrow in each program and why each other list did not. Commit, push, wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_narrow_int.py` passes in all three builds.
- tree_fold's peak RSS with `AIL_NARROW_INT=1` meets the target, or `NARROW_RESULTS.md` names the list that stayed
  int64 and the use that blocked it.
- 0 output differences on the 10 tasks with the variable set; 0 hash differences on the 110 programs without it.
- The 20 shards pass; `git diff --stat origin/integ` shows only the files above.

## Stop rule

Stop on any wrong output. Record the program first. If one operation needs more than the 120 `pyfunc.py` lines, drop it
from the set (the list stays int64) and report it. Stop when 60 minutes pass. Push what is done first.

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
- Lists: `ail_list` is `{int64_t *p; ail_len_t n, cap;}` (`cruntime.py` ~line 204), `ail_slist` holds a 24 B
  `ail_str` per element (~2946), `ail_pslist` is the dense str list (~4137). List buffers carry no refcount.
- `lab/rc/PRICE.md` (rc1): list buffers are 95% of tree_fold's peak (384 of 404 MiB); class objects already reuse
  memory through the per-size pool (`ail_pool_head`). `docs/design/ARENA1.md`: after arena1s1-s4 the runner peak is
  405 MiB; "the 8-byte ints make every temporary 2x the size of C's int32".
- tree_fold: `lab/compare/src/tree_fold/typed.py`, input from `lab/compare/tasks/tree_fold/gen.py` at N = 3,000,000.
  Rust's peak RSS on compare-lab 2026-10-31: 315 MiB. The owner's bar: AIL must beat Rust on peak RSS too.

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
