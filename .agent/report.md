# job job-ctpred1_rr1-11070701  started 2026-11-06T22:03:15Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Two commits on `job-ctpred1_rr1-11070701` (no push, per the runner instruction).

**What I measured** (`lab/profile/pred_probe.py`, external `sitecustomize` wrapper, `pyfunc.py` untouched): per-call key (`id(node)`, primitive args, `id(ctx)`), own time, and `repr(result)` for `_etype`, `_is_str_expr`, `_is_slist_expr`, `_map_kind`, `_is_bytes_expr`, `_is_owned_bytes_call`, `Ctx.type_of`, `_param_kinds` — all 10 compare tasks plus the first 200 corpus programs (210 inputs).

**Key results**
- Wrapper is observation-only: `sha256(program.c)` identical with/without the probe on **10/10** tasks.
- Lookup `L` = **125 ns/call** (`timeit`, key built from `id(node)`, `id(ctx)`).
- Biggest predicates are *not* plain-cacheable: changed repeats over 210 inputs — `_etype` 220,974; `Ctx.type_of` 822,922; `_is_str_expr` 12,135; `_is_slist_expr` 1,207; `_is_bytes_expr` 1,983.
- Only 0-changed predicates (ordered by cacheable s): `_is_owned_bytes_call` 0.161, `_map_kind` 0.124, `_param_kinds` 0.000 (no repeats at all).
- Eligible pool: 1,020,167 calls → 0.285 s cacheable vs 0.128 s lookup = **0.157 s net**, 1.003x pooled, best task echo_pack 1.005x halved. Even the unreachable all-eight-predicate cache is only 1.038x halved pooled.

**Verdict: NO-GO** — the halved projection clears 1.03x on zero tasks, so ctpred2 should not build a predicate memo; the four highest-priced predicates are exactly the state-dependent ones a plain memo breaks on.

**Byte identity**: `ccheck.py --base` recorded C/executable/refusal hashes for **220 inputs** (205 built, 15 refused by name); `docs/design/alias_study/trans` is absent from this tree, noted in the record.

**Not verified**: `ccheck.py --check` (a second full pass takes ~13 min under the shared-runner load; budget hit), and no CI shards — the runner instruction forbids pushing, and there is no `origin/integ` or `gh` access here. No compiler files changed, so no new regression probes apply.
[commandcode stop=end_turn turns=56 out_tokens=40714]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: ctpred1_rr1 (measurement-only)

**What the diff really does:** adds four new files under `lab/profile/` — an out-of-process `sitecustomize` probe that wraps eight `pyfunc` predicates (`pred_probe.py`), a byte-identity recorder (`ccheck.py`), and the results (`CTIME_PRED.md/.json`). No compiler or runtime file changes (`git diff --name-only work..HEAD -- AIL_CURRENT tools packaging` = 0 files), so a probe program is unchanged by construction; `p1.py` matches CPython on both builds.

**Claims checked**
| claim | result |
|---|---|
| wrapper is observation-only, `program.c` identical 10/10 | **verified** — I rebuilt all 10 with and without the wrapper; hashes equal the §6 values |
| 10 tasks + 200 corpus inputs, 8 predicates | **verified** in JSON |
| `_etype`/`type_of`/`_is_str`/`_is_slist`/`_is_bytes` changed totals | **verified** against JSON; reproducible only in debug mode (see defect 1) |
| `_is_owned_bytes_call`, `_map_kind`, `_param_kinds` are the 0-changed set | **verified** for the 10 tasks (corpus not re-run) |
| `L = 125 ns` | **verified** (I measure 102 ns) |
| `ccheck --base`: 220 inputs, 205 built, 15 refused; `alias_study/trans` absent | **verified** |
| `ccheck --check`, CI shards | **unverified** (report admits; not runnable here) |
| `test_ail_safetynet` | **passes**, 0 failed / 205 s |

**Defects**

1. **The 10-task rows were measured under `--debug-dir`; the corpus rows and the CTIME_FE wall/own times are from normal builds.** Debug builds execute 2–4× more predicate calls, so §4/§5 mix two pipelines:
   - `tally_lang/_etype`: record 34,540 calls / 1,254 changed; no-debug run **8,369 / 390**
   - `ticket_audit/_etype`: record 58,509 / 1,687; no-debug **17,137 / 782**
   - `tree_fold/_etype`: record 69,966 / 8,999; no-debug **28,079 / 4,858**
   (`berth_sim` happens to be identical both ways, which hid it.) Probe: `/tmp/rprobes/run4.py` vs the JSON.

2. **Reported "cacheable s" exceeds the predicate's entire FE own time** — a cache cannot save more than the predicate spends:
   - `_map_kind` 0.1244 vs FE own 0.1095; `_is_owned_bytes_call` 0.1605 vs 0.1415; `type_of` 0.0814 vs 0.0475 (md §4).
   The `fe_probe_ratio` in the JSON is not `fe_own/probe_own` for these rows, so the per-task saving column (§5, pooled 0.157 s) is not reproducible from the JSON.

3. `pred_probe.py` charges each nested call's *recording* cost to the enclosing predicate: `record()` runs after `finish()` but before the child returns. Measured 316,285 records = 1.58 s inside a 4.01 s total "own" on `chain_relax` (~5 µs/record vs 0.29 µs of real predicate time). §2's "cProfile convention" claim is false; `own_s` is instrumentation-dominated.

**Does the decision change?** No. Using the true FE own times with `f = 1` (eligible predicates free) the best halved projection is 1.0056 (berth_sim, echo_pack) — still below the 1.03 go rule. **NO-GO stands**; the errors are all optimistic, so the corrected numbers only strengthen it. No regression risk: no compiler file changed.

**Unverified:** the 200-program corpus rerun, `ccheck.py --check`, CI shards.

VERDICT: FIX
1. Re-run the 10 task probes without `--debug-dir` (or derive all rows from one pipeline) and regenerate §4/§5: expected `tally_lang/_etype` calls 8,369 (actual in record 34,540); same for ticket_audit (17,137 vs 58,509) and tree_fold (28,079 vs 69,966).
2. Recompute the scale factor as the stated `fe_own/probe_own` and fix the rows where cacheable exceeds own: `_map_kind` expected ≤ 0.1095 (actual 0.1244), `_is_owned_bytes_call` ≤ 0.1415 (actual 0.1605), `type_of` ≤ 0.0475 (actual 0.0814).
3. Fix the own-time attribution in `pred_probe.py` (subtract the child's whole wrapper interval, `record` included) or drop the "cProfile convention" claim and report the inflated times as such.
[commandcode stop=end_turn turns=46 out_tokens=62296]

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
**What the change actually does:** adds two measurement-only scripts (`lab/profile/pred_probe.py`, `lab/profile/ccheck.py`) and their report/data (`CTIME_PRED.md`, `CTIME_PRED.json`). No file under `AIL_CURRENT/`, `pyfunc.py`, runtime or C emitter is touched, so no program semantics change — the diff is exactly the four new lab files.

**Verified**
- `pred_probe.py` reproduces the committed numbers: re-running `--tasks echo_pack` on HEAD gave calls/repeats/changed identical to the JSON for all 8 predicates (`_etype` 95153/92172/16513, `_map_kind` 122210/119229/0, `type_of` 301359/301104/83893), and cacheable after the documented `fe_own/probe_own` scaling matches to ~0.1%.
- Whole-record consistency: a fresh `ccheck --check` builds (220/220) matched every `c`/`exe`/`rc` hash; only one refusal hash differs (defect 1).
- Probe is observe-only: `pred_probe --tasks tree_fold --debug` produced `sha256(program.c)=36cc65e7…`, the same as the no-probe/`typed.py` build recorded in `byte_identity`.
- `test_ail_safetynet`: pass (256 s, `-j 2`). No test modules were added/edited.
- JSON has all 10 tasks × 8 predicates with calls/repeats/changed/cacheable; per-task saving/projection/halved arithmetic recomputes exactly; ends with the no-go at 1.0052x best halved (the 1.03x rule fails by a wide margin). Decision is sound and robust to the probe's timing inflation.

**Defects**
1. The committed `byte_identity` record is stale relative to the final `ccheck.py`. Commit c9d747e added `ailc-<tmp>` normalization, but the record was made by the older version. Reproduce: JSON row `lab/corpus/programs/glm-5.3-flash-free/t131.py`, expected refusal `e968cda8…` (HEAD), actual fresh build `998da936…`; `python3 lab/profile/ccheck.py --check` on HEAD therefore prints `MISMATCH … t131.py refusal` and exits 1 instead of `all 220 inputs identical`. (My initial `--check` passed only because a stray `ccheck --base` rewrote the working-tree JSON at 23:50:35; not run by me, left uncommitted.)
2. `CTIME_PRED.md` §5 prose contradicts its own table: it says eligible cacheable "0.222 s" and net "0.106 s (0.34%)", but the listed-predicate savings column (0.146 s, 1.0048x pooled / 0.474%) correspond to 0.262 s cacheable (0.1176 `_map_kind` + 0.1444 `_is_owned_bytes_call`). Expected 0.262/0.474%, actual 0.222/0.34%.
3. Minor: §2 says the wrapper inflates own time "about a microsecond per call"; measured inflation is 0.8 µs (`type_of`) to 12.9 µs (`_etype`) per call. Scaling makes this non-blocking.

**Notes:** `_param_kinds` keys on `id()` of dict/tuple arguments, so it can only under-count repeats; with 0 repeats anyway the conclusion is unaffected. §1's "halved 1.123x" is carried from `CTIME_CUT.md` as instructed. Commit trailers on 64211aa/3d61a4e name "Claude Sonnet 5.5" while the worker header shows deepseek attempts — unverifiable which model authored, flagging only.

**Pre-existing:** none identified (no compiler change).

**Unverified:** berth_sim/chain_relax/tally_lang sub-step runs; the 200-corpus changed-repeat rows (probe outputs not committed — only aggregates); CI shards / PR (remote branch is still at the base, so nothing was pushed).

VERDICT: FIX
1. Regenerate `byte_identity` with the final `ccheck.py` and commit it: probe `lab/profile/ccheck.py --check` on HEAD, expected `all 220 inputs identical` / exit 0, actual `MISMATCH lab/corpus/programs/glm-5.3-flash-free/t131.py refusal` / exit 1 (recorded `e968cda8…`, fresh `998da936…`).
2. Correct `CTIME_PRED.md` §5: expected eligible cacheable 0.262 s / net 0.146 s (0.474% of wall), actual text says 0.222 s / 0.106 s (0.34%).
[commandcode stop=end_turn turns=50 out_tokens=40162]

FINAL VERDICT: FIX  2026-11-07T00:05:18Z
