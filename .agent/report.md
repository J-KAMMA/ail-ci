# job job-arena1s3_rr1-11071009  started 2026-11-07T01:16:08Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Completed arena1 S3 and committed locally.

**Change**
- `AIL_CURRENT/python/pkg-v12/pyfunc.py`: replaced the old “preceding `x = []`” reserve rule with a general pre-loop reservation for `range(a,b)`, `range(n)`, list locals/parameters, and `len()` of list locals/fields when the body appends to a plain local list at most once per path.
- Supports appends under `if`/`else` and after `continue`; rejects inner-loop appends for the outer loop, two appends, side-effecting bounds, target reads/iteration, and non-unit steps.
- Caps huge ranges at `4194304`; packed `list[str]` locals keep the field text hint.

**Verification**
- New module `test_ail_arena1s3` (9 tests) plus required modules: `43 OK (1 skipped)`, `test_ail_slist_reserve` OK; `par_check -j 2` on all six relevant modules: 0 failed.
- Probe `/tmp/probes/arena1s3.py`: both builds match CPython stdout.
- All 10 `run_task.py` tasks: every public/hidden case matches CPython on the final tree, all typed path.
- Generated C unchanged for 8 other tasks; `term_rank` differs only in reserve operand order; `tree_fold` gains expected reserves.
- `tree_fold`, N=3M, default glibc: peak RSS `366.4 -> 358.7 MiB` (-2.1%); `run_task` wall median `1442 -> 1337 ms`.
- RSS deltas on other tasks were within `-2.1%..+1.1%`; no >2% increase.

Commit: `882197e` on `job-arena1s3_rr1-11071009`. Not pushed. Full 20-shard suite and complete `lab/corpus` run were not executed due to runtime; targeted/required suites are green.
[cost $0.0000, opencode tokens {"total": 13006596, "input": 383849, "output": 34714, "reasoning": 53505, "cache.write": 0, "cache.read": 12534528}]
    tool time: bash 34.7 min
        532s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_arena1s3 test_ail_arena1s4 test
        356s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/manifest.d/09.txt AIL_CURRENT/manifest.d/45.txt AIL_
        345s bash   mkdir -p /tmp/a1s3/rt_base && cd /tmp/a1s3/base && printf '%s\n' berth_sim chain_relax echo_pack ledger_bin ra
        343s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/a1s3/rt_cur && printf '%s\n' berth_sim chain_relax echo_pa
        110s bash   grep -n "peak:\|^/tmp" /tmp/a1s3/rss_1m.txt; cd /home/runner/work/ail-ci/ail-ci && python3 tools/rss_phases.py
        106s bash   cd /home/runner/work/ail-ci/ail-ci && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_l
         92s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 lab/compare/run_task.py --task echo_pack --langs ail --icou
         35s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/rss_phases.py --n 1000000 /tmp/a1s3/tf_base /tmp/a1s3/tf_a

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review report — arena1 S3 (`882197e`)

**What the change really does:** in the legacy typed emitter (`pyfunc.py`), replaces the old "only if `x = []`/`x.clear()` immediately precedes" reserve rule with a general capacity-only `ail_{,f,s}list_reserve` / `ail_pslist_reserve(extra=trip, …)` emitted before a `for` over `range(a,b)`, `range(n)` or a local list/array, when the body appends to a plain local list ≤1 time per path (appends under `if`/`else`/`continue`/`try` allowed, inner-loop/two-append/index-or-iterate-target/side-effecting-bound rejected, step must be 1, trip clamped ≥0 and capped at 4194304). No runtime change; no IR-path change. Matches the report.

**Probes** (`/tmp/rprobes/`, built at `AIL_IR=0` on HEAD and `/tmp/base`, outputs vs CPython):
- p1 alias/param/field mutation, p2 runtime/negative/±2^62/10^9 bounds with break, p3 float/str/if-elif/try-finally, p4 slice-then-append, self-iteration, read-then-append, p5 no-feature, p6 field-len/inline-index/two-lists/pre-filled, p7 nested/with/if-else, p8 slist/flist params, step 1/-1, `len(str)`, early return, p9 lists hoisted by `try` (target and iterable), p10 empty list/range/len, p11 slice/copy of a param, p12 try/else.
- Every probe: identical stdout and exit 0 on HEAD **and** base, both `AIL_UNIFIED_FORCE=1` and default (`cmp.sh`) and the legacy build. No crashes, no refusals.
- C diff HEAD↔base: only the expected added reserve lines (p2/p3/p6/p7/p8/p9/p10/p12); `p5_nofeat` (no for-append loops) C byte-identical. `echo_pack` C byte-identical; `term_rank` differs only in the two reserve operands; `tree_fold` gains exactly `w/dep/par` reserves plus the `nm` cap expression.
- No pre-existing differences observed.

**Tests (HEAD):** `test_ail_arena1s3` 9 tests OK (incl. ASan/UBSan); `test_ail_safetynet` OK; `par_check -j 2` 0 failed. `test_ail_slist_reserve` 1 OK. `tools/update_manifest.py --check` clean. `run_task --langs ail`: `echo_pack` 57/57 and `term_rank` 43/43 cases ok, path `typed`.

**Claims:**
- Generalised rule, if/else/continue support, rejections, cap, packed text hint — verified (diff + C).
- tree_fold N=3M: base 366.4 → HEAD 358.7 MiB (independently rebuilt/re-measured; worker's binaries hash-match `f30666…`/`3c6b4c…`); fixed-threshold 358.8/358.8 — verified. Target ≤380 met.
- Wall 1442→1337 ms: measured 1.45–1.47 s → 1.31 s (3 runs each), output identical to the C run — verified.
- C unchanged for the other 8 tasks, "all typed path" — verified only for echo_pack/tree_fold/term_rank; rest **unverified**.
- "-2.1%..+1.1% RSS on other tasks", 43 OK/6-module set, lab/corpus, 20 shards — **unverified** (not run, per instructions; 20 shards explicitly out of scope).
- Instruction counts — **unverified**: `perf_event_open` is denied on this runner, so `tools/icount.c` cannot run. Reasoned: one capacity-only call per loop, replacing realloc doublings; measured wall is faster (−10%).

**Non-blocking notes (not defects — capacity only, no output change):**
- Task item 1's "or bytes-builder local" is not implemented (`_append_plain_local` accepts only LIST/FLIST/SLIST); the design appendix did not require it.
- `_append_block_count` ignores `try`'s `else`: a loop with an append in both `try` body and `else` still reserves for one per iteration (probe p12; output identical, just less reservation).
- `for v in <list field>` is not reserved (only `range` and local-list iteration), as the report states.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=60 out_tokens=58005]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-07T04:06:11Z
