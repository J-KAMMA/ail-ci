# job job-fbregion1-11090339  started 2026-11-08T18:41:19Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Here's the short report.

## fbregion1 — measurement only

**Commits** (branch `job-fbregion1-11090339`, not pushed per the runner instruction):
- `0ed8e9d` — census + price
- `ededa74` — doc corrections

**Files** (only these): `lab/mem/REGION.md`, `lab/mem/REGION.json`, `lab/mem/region_census.py`.

### (a) Dynamic census — 16/16
All 16 tracked builds (scratch `program.c` only) matched the plain `-O2` build byte-for-byte with the same exit status. Same-iteration heap (real malloc/calloc→free) pairs:

| program | pairs | share of run instructions | halved projection |
|---|---:|---:|---:|
| term_rank | 16,194,761 | 4.177% | 1.0129x |
| tree_fold | 1,768,062 | 0.305% | 1.0009x |
| berth_sim | 1,186 | ~0 | 1.0000x |
| ticket_audit | 813 | ~0 | 1.0000x |
| rail_transfer | 131 | ~0 | 1.0000x |
| all 6 object programs | 0 | 0 | 1.0000x |

- term_rank's churn is `ail_barena_push` pointer tables (7.80 M) + `ail_bytearray_freeze` payloads (7.80 M) + 0.60 M str blocks.
- ticket_audit's 19.9 M `ail__bpay_release` are arena/cache traffic: only **1** same-iteration heap pair. rc1's 0.069% share is consistent.
- Class objects are pool-served: objscan 500k allocations, 0 heap pairs; linkedlist/rbtree likewise 0. A region adds nothing there.

### (b) Static census
64 allocation sites in 15 programs (`chain_relax` has no allocation expression): **7 static yes**, 11 in-loop but blocked, 46 not in a loop. Blockers: 7 stored into a container/field, 2 closure/comprehension capture, 1 for-loop iterable live across the back edge, 1 passed to a non-borrowed callee. `ir/borrow.py`, `ir/ownership.py`, `ir/effects.py` imported read-only.

### (c) Price / go-no-go
**fbregion2: NO-GO.** Best halved instruction projection is **1.0129x** (term_rank), below 1.03x. The ≥5% peak-RSS test is met mechanically on 5 programs, but four are one-shot buffers (echo_pack 34.0 MiB/2 pairs, ledger_bin 64.9 MiB/3, scar_life 8.0 MiB/8, tree_fold 22.9 MiB from a 24 MB single snapshot); only term_rank (8.0 MiB, 5.06%) is genuine churn — one program, short of two.

### Limits / verification
- **Loud stop on the instruction value**: no CPU PMU (`perf_event_open` fails) and no `valgrind` on this runner. The `s` column uses rc1's gcov-based total as denominator only, labelled an estimate; pair counts are exact.
- Probes: no language/compiler behaviour changed; the 16 tracked-vs-plain output comparisons are the equivalence check.
- Tests: `test_ail_safetynet` OK, `test_ail_files` OK (1 skip). `test_ail_corpus_findings3` did not finish within the 420 s slice and was stopped; I left no background jobs.
- `git status` is clean except the pre-existing untracked `.agent/pipeline.md`; the commit touches only `lab/mem/`. CI shards could not be run because this runner says not to push/open a PR.
[commandcode stop=end_turn turns=154 out_tokens=128566]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: fbregion1 (measure-only)

**What the diff really does:** adds `lab/mem/region_census.py` (a C-source instrumentation harness + a Python static-rule script) and the reports `REGION.md`/`REGION.json`. No compiler/runtime file is touched (`git diff --name-only work..HEAD` = the 3 `lab/mem/` files), so no generated C can change; a base worktree comparison is vacuous. Speed step N/A.

### Defect 1 — the dynamic "same-iteration" predicate is wrong (stale current-loop)

`rt_cur` is set by `rt_tick` at loop entry and never restored on loop exit; helper allocations (`loop == 0` lexically, which is *every* `bytes`/`bytearray`/`str` payload) are then attributed to `rt_cur`.

Probe `/tmp/rprobes/stale.py` (allocation outside any loop, after a `for`):
```
def main() -> int:
    s = 0
    for i in range(3):
        s += i
    b = bytes(100000)
    print(len(b), s)
    return 0
main()
```
- expected: not iteration-local (no loop) → `heap_same_iter = 0`
- actual (unmodified script): `totals {'same_iter': 2, 'heap_same_iter': 2}`, `ail_bytes_zeros loop 27 same 1 heap_same 1`

Re-measured with loop entry/exit tracking added (`rt_leave` restoring `rt_cur`; scratch copy only):
- `stale.py` → `heap_same_iter 0` (correct), `keep.py` (list-retained bytes) unchanged at 1/3.
- `tree_fold` → `heap_same_iter 14`, **not 1,768,062**; `same_iter 17` vs 1,768,065.
- `term_rank` → `heap_same_iter 16,494,282` vs 16,194,761 (+1.85%).

tree_fold's "1.77M int-to-str pairs" is definitively an artifact: the generated C frees the previous iteration's payloads at the top of the next iteration —
`for (k2…) { v_i = k2; ail_sarena_keep_roots(&v__sarena, _fmark1, _froots1, 0); … ail_str_from_int(...) … }` (program.c:8563–8583), i.e. those temps cross the back edge and are **not** iteration-local. The tool attributed them to loop 57 (`while (m)` inside `ail_str_from_int`, which has already exited).

### Defect 2 — the static rule is not implemented as stated

`_uses()` treats the allocation's own binding as the rebind cutoff (`first_store == alloc line`), so no later use of a named target is ever inspected; temporaries default to "yes".

Probe `/tmp/rprobes/stat.py` (field store, list store, pass-to-callee, return):
```
class Box:
    def __init__(self) -> None:
        self.v: bytes = b""
def take(x: bytes) -> None:
    return None
def f(b: Box, lst: list[bytes], n: int) -> int:
    for i in range(n):
        a = bytes([65]); b.v = a          # stored into a field
        c = bytearray(); c.append(66); lst.append(c)   # stored into a list
        d = bytes([67]); take(d)
        e = bytes([68]); return len(e)    # returned
    return 0
```
- expected: no, blocked by field/list/return
- actual: `11 bpay YES`, `13 bpay YES`, `16 bpay YES`, `18 bpay YES` — all four local.

Also inconsistent inside the tool: `term_rank main:138` tuple (in a sort lambda) is "yes", while the identical tuple-in-lambda at `rail_transfer solve:93/95` is "no (captured in a closure)". `ir/ownership.py` and `ir/effects.py` are imported but never used; "live across the back edge" is only a line-range test. The "7 static yes / 11 blocked / 46 not in loop" counts reproduce exactly, but they are the output of a rule that does not apply the stated conditions.

### Defect 3 (minor) — the go/no-go rests on the forbidden instrument

The `s` column divides by rc1's **gcov estimate** ("never a gcov estimate" for go/no-go numbers). No PMU and no valgrind is verified true on this runner, so the number cannot be calibrated here; the honest output is "not computable", not 1.0129x. The NO-GO conclusion is robust regardless: with defect 1 fixed, term_rank ≈ 4.25% → 1.0131x, tree_fold → ~1.0000x.

### Pre-existing
None (no compiler change, no output differences).

### Tests
`test_ail_safetynet` on HEAD: **ok, 176s, 0 failed**. The change adds/edits no test modules.

### Claim check
- "16/16 tracked builds match the plain build" — verified by re-running term_rank, tree_fold, cfold (all `match True`, identical counts).
- term_rank 16,194,761 / 4.177% / 1.0129x — reproduced, but predicate wrong (+1.85% corrected).
- tree_fold 1,768,062 pairs / 0.305% — **false**; correct ≈14.
- ticket_audit `bpay` 19,874,065 allocs, 2,860,802 same-iter, 1 heap pair; `ail_bytes_hex` 7,784,974 same-iter, 7 heap — verified.
- Class objects pool-served, 0 heap pairs — verified (objscan 500k, binarytrees 16,369, linkedlist 200k, rbtree 100k).
- "no PMU, no valgrind" — verified.
- 64 sites / 15 programs; rc1 9.35M / 2.413% / ticket 0.069% — verified against `lab/rc/PRICE.md`.
- Only `lab/mem/` touched — verified.

Unverified: the "busy/shared" status of the files fbregion2 would edit; `test_ail_corpus_findings3` (not in scope for me to rerun); whether the one-shot-buffer judgment is the owner's intended reading of the RSS route.

VERDICT: FIX
1. Dynamic census misattributes allocations via stale `rt_cur` (`region_census.py` PROLOGUE `rt_alloc_hook` / `rt_tick`): expected `stale.py` heap_same_iter 0, actual 2; expected tree_fold heap_same_iter 14 (proved by `ail_sarena_keep_roots` at program.c:8565), actual 1,768,062. Add `rt_leave`/push-pop so `rt_cur` is the enclosing loop at the allocation point, then regenerate REGION.md/json.
2. Static rule not implemented (`_uses` rebind cutoff): expected the four sites in `/tmp/rprobes/stat.py` to be blocked (field/list/return), actual all "YES"; the 7-site count and table (b) must be re-derived after fixing the cutoff and the temporary/closure handling.
[commandcode stop=end_turn turns=72 out_tokens=61639]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

## review 1
[model commandcode/deepseek-v4.1-flash]
I have everything I need. Final checks are complete.

## Review: fbregion1 (measure-only region census)

**What the change really does:** adds three files under `lab/mem/` — `region_census.py` (builds each of the 16 programs with `--debug-dir`, instruments a scratch copy of `program.c` with loop/iteration counters and allocator hooks, reports same-iteration frees; runs a source-level static rule over `ir/borrow.py`; computes the rc1 price), plus the generated `REGION.md` and `REGION.json`. No compiler or runtime file is touched. This matches the stated intent (measure only).

**Verification of claims (worker's chat report is empty; claims read from REGION.md):**
- "No compiler/runtime changed" — **verified**: `git diff work..HEAD` is only `lab/mem/`; generated C for `tally_lang` is byte-identical between base (`/tmp/base2` @ `work`) and HEAD.
- "16/16 programs; tracked stdout/exit == plain" — **verified**: I re-ran the full census; all 16 printed `True`, and every program's totals and all 115 dynamic sites were identical to the committed `REGION.json`.
- Main/per-kind/price tables and RSS% — **verified** against `REGION.json` (0 mismatches); `tree_fold` heap peak 24,000,000 B = 5.66% RSS, one-shot.
- Static census: 64 sites, 6 yes, 12 blocked, 46 not-in-loop; blocker counts 7/3/1/1 — **verified** from JSON; script calls `borrow.analyze(tree)` and flags `__del__`.
- "Instruction route not computable" — **verified**: `/sys/bus/event_source/devices` has no `cpu`; `valgrind` absent; `tools/icount.c` uses `PERF_COUNT_HW_INSTRUCTIONS`.
- Price formula (pairs·170/est, Amdahl, roof 0.6, halved) and **NO-GO** — **verified**: max halved projection 1.0124x (term_rank) < 1.03x; RSS route has only `tree_fold` ≥5% and it is a one-shot bulk peak, so <2 programs.

**My probes** (`/tmp/rprobes/`, run through the script's own `one_program`):
- `reg_after.py` — `bytes(100000)` after a 3-iteration loop → `same_iter 0, heap 0` (corrected predicate; loop-0 allocations excluded). Pass.
- `reg_local.py` — 1000× `bytes([65])` → allocations land in a barena freed in bulk, so 1 same-iter; matches the documented "actual free" semantics. Pass.
- `reg_break.py`, `reg_nest.py` — continue/break and nested-loop attribution correct (loop ids distinct). Pass.
- `reg_escape.py` — a program that falls back to AIL's general/GC path (uses `ail_xmalloc`, no typed allocators): instrumentation fails loudly (`tracked compile failed`), not silently wrong. None of the 16 is general-path, so this is a tool limitation, not a defect in the delivered numbers.
- `bash ~/tools/cmp.sh lab/rc/progs/cfold.py` — matches CPython in both general and default builds.

**Tests:** `test_ail_safetynet` — 1/1 ok (169s), `-j 2`.

**Pre-existing:** none found (C unchanged; no compiler paths influenced).

**Not checked:** the 20 CI shards (not run per instructions); a full per-program CPython diff for all 16 (the change cannot alter their C, since it edits nothing the compiler reads, and `cfold` was spot-checked).

Note: the worker produced no final chat report, but the required numbers are all in `REGION.md`/`REGION.json` and they reproduce exactly.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=56 out_tokens=35718]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T21:43:48Z
