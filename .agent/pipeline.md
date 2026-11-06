# job job-roof1-11070417  started 2026-11-06T19:18:36Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Here's the report.

## What I fixed

**Defect 1 — wrong input program.** `measure.py` built `typed.py`; it now builds both compare-lab AIL columns: `ail` = `typed.py`, `ail-py` = `main.py` (the task's source). `main.py` gets `--exact-int` for `rail_transfer`/`chain_relax` and for any file with an `# ail-build: --exact-int` directive — `scar_life` otherwise builds and dies at runtime with `OverflowError`. `vec.py` surveys both sources; `--merge` preserves the other column.

**Defect 2.** `0.85x–5.40x` → `0.83x–5.40x` (`term_rank` is the minimum); `other 54–95%` → `54–100%` (`chain_relax` is 100%).

**Defect 3.** History was squashed to one commit, so the wrong trailers are gone; the new commit has no `Co-Authored-By` line. This report carries the probe list the review said was missing.

## Measured result (`main.py`, the task's source)

| | |
|---|---|
| builds that compile | 8 of 10; 6 are **boxed general path** |
| refusals | `tally_lang` (compiled pattern TOK used as a value), `tree_fold` (suite pattern NODE + tuple element type) |
| wall vs C | **1.6x–143x, median 9.9x** (typed `typed.py` is 0.67x–1.98x) |
| same program vs its typed build | up to **122x** (`chain_relax` 153.8 s vs 1.263 s; `ledger_bin` 48.8 vs 0.884; `ticket_audit` 57.0 vs 1.760) |
| counters | `berth_sim` 33.476e9 Ir/250.6M LLC, `echo_pack` 18.231e9/36.4M, `rail_transfer` 3.704e9/23.3M, `term_rank` 111.51e9 Ir (IR-only); the rest exceed the 20-min cachegrind cap and are `n/m` |

## Probes and checks

- `measure.py --tasks echo_pack --langs ail-py` → **source `main.py`**, builds, typed path, 5.31 s.
- Review's numbers reproduced: `ledger_bin` 48.85 s (review 47.96), `ticket_audit` 57.0 (51.85), `echo_pack` 5.02–5.77 (5.23); C unchanged.
- `/tmp/roofchk/equiv.py` — all **8 compiled `main.py` binaries produce byte-identical stdout and rc=0** vs C on the perf input.
- `scar_life` without the directive → rc=1, named `OverflowError … --exact-int`; with it → rc=0, 30.9 s.
- `tools/par_check.py -j2 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → **3 modules in 348 s, 0 failed**.
- `update_manifest.py` and `--check` → 0; only `DEVLOG.md` and `lab/roof/*` changed; no compiler/bench diff.

Not verified: cachegrind counters for the four largest general-path builds (`n/m`, documented), a single-job end-to-end `run.sh` (machine facts/typed column come from the earlier job on the same runner type), and attribution of the `main.py` general path (still `typed.py` only, stated in RESULTS).
[commandcode stop=end_turn turns=126 out_tokens=66137]

## review 0
[model commandcode/deepseek-v4.1-flash]
## What the change really does

It is still measurement-only: `lab/roof/measure.py` now builds both compare-lab AIL columns (`ail`=`typed.py`, `ail-py`=`main.py`, which is the source the task names), with `--exact-int` for `rail_transfer`/`chain_relax` plus any `# ail-build:` directive (`scar_life`); `vec.py` surveys both sources; `--merge` preserves the other column; RESULTS/DEVLOG gain a `main.py` table and the two corrected ranges. `git diff work..HEAD -- AIL_CURRENT tools packaging bench` is empty; only `DEVLOG.md` and `lab/roof/*` change.

## Review-1 defects

1. **Wrong input program — fixed and reproduced.** `measure.py --tasks rail_transfer --langs ail-py --runs 1 --no-cache` prints `source main.py`, wall 0.9887 s, `path general`, matching the recorded 0.9618 s; `tally_lang`/`tree_fold` are named refusals with the exact messages stored in `programs.json`. Data is internally consistent: 8 of 10 build, 6 `ail-py_path=general` (chain, ledger, rail, scar, term, ticket), 2 typed (berth, echo), all 8 `ail-py_rc=0`. Recomputed from `programs.json`: wall vs C = 1.62, 2.76, 9.16, 9.32, 10.49, 64.2, 72.2, 143.2 → **1.6x–143x, median 9.9x** ✓; typed column 0.669–1.983, median 1.31 ✓.
2. **Ranges — fixed.** Typed instruction ratios recomputed: 0.826 (term_rank) to 5.404 (ticket_audit) → `0.83x–5.40x` ✓; `delta.other/total` = 53.8, 61.7, 76.2, 95.0, **100.0** (chain_relax) → `54–100%` ✓. No stale `0.85x`/`54–95%` survives (RESULTS line 166's `0.85x` is a wall ratio).
3. **Process — fixed.** The fix commit carries no `Co-Authored-By`; the report has a probe list. (The branch now contains only `work` + one commit; the old trailer-bearing commits are not in `work..HEAD`.)

Other report claims verified against the data: 33.476e9 Ir/250.6M LLC (berth), 18.231e9/36.4M (echo), 3.704e9/23.3M (rail), 111.51e9 Ir = 30% of the 4-IPC floor (term); 1 vectorised loop only in scar_life and term_rank; typed `other` 54–100%; `update_manifest.py --check` rc=0.

## Probes and tests

- `measure.py --langs ail-py` probe (above): builds `main.py`, general path, correct wall.
- `--merge` probe on a copy of `programs.json`: re-measuring `ail` kept `ail-py_source=main.py`, `ail-py_wall_s=0.9618`, `ail-py_path=general`; refreshed only `ail`.
- Compiler change check: compiled `/tmp/rprobes/p_list.py` on HEAD and on `git worktree add /tmp/base work`; emitted `program.c` **byte-identical** (`C_IDENTICAL`); `cmp.sh` gives CPython-matching stdout on both builds. As expected, since no compiler/runtime file changed.
- Base confirms the two `main.py` refusals are pre-existing (`tally_lang` rc=3 with "the compiled pattern TOK is used as a value").
- `par_check.py -j 2 test_ail_safetynet` → `1 modules in 184s, 0 failed`. I did not repeat the worker's 3-module run.

**Minor, not blocking:** the `main.py` table has no C row of its own (C rows are in the typed table, same binaries); entries for the `ail` column written before this fix lack `ail_source` (cosmetic `None` in the printed table); `--merge` would keep a stale `*_wall_s` if a re-run's build fails. None affects the committed numbers.

## Pre-existing

`tally_lang`/`tree_fold` `main.py` build refusals (compiler unchanged; reproduced on base). No new compiler/runtime difference exists to compare.

## Unverified

- Worker's "byte-identical stdout for all 8 `main.py` binaries vs C on the perf input" (`rc=0` is in the data; stdout not re-diffed here).
- `scar_life` without `--exact-int` dying with the named `OverflowError` (30 s run not repeated).
- Full `run.sh` and the machine-facts/C/typed re-measurement in this job (disclosed in RESULTS).
- Speed: not applicable — the change touches no hot code (only `lab/roof/` and DEVLOG).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=27 out_tokens=20105]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T21:41:36Z
