# mypyc1: results — the price gate fired before the trial

Measure-only. No compiler, runtime or test file was changed. Base `origin/integ` (`f369daa`; the
worktree export is `73dedad`, and `lab/profile/CTIME_FE.{md,json}` are byte-identical between
them).

## 1. Outcome

| item | value |
|---|---|
| pilot pick | `rangecheck.py` (largest own-time share of any non-excluded compiler module) |
| price, pooled | 0.997 s own of 30.795 s cold wall = 3.24%; full 1.0109x, halved 1.0055x |
| price, best task | scar_life: 0.239 s of 1.641 s = 14.57%; full 1.0510x, halved 1.0255x |
| tasks >= 1.03x halved | 0 of 10 |
| trial compile | **not run** — the brief's stop rule fired at the price stage |
| achieved | not measured (no `.so`, no mypyc build) |
| achieved / price | not applicable |
| C / refusal hashes over 120 inputs | **not run** (no compiled copy; cannot claim 0 differences) |
| compiler instruction count before/after | **not run** (no "after" build) |
| go/no-go for mypyc2 | **NO-GO for a single free-module pilot** |

## 2. Why the stop rule fired

`PRICE.md` has the full arithmetic. In short, with the assumed 1.5x roof on the module's own
Python time and the repo's halving rule, a module clears 1.03x only when its own time is at least
17.0% of the cold wall on at least one task. No non-excluded module reaches that:

| task | `rangecheck` own s | share | full | halved |
|---|---:|---:|---:|---:|
| berth_sim | 0.430 | 4.94% | 1.0167 | 1.0084 |
| chain_relax | 0.025 | 1.74% | 1.0058 | 1.0029 |
| echo_pack | 0.055 | 2.35% | 1.0079 | 1.0040 |
| ledger_bin | 0.030 | 1.23% | 1.0041 | 1.0021 |
| rail_transfer | 0.028 | 1.34% | 1.0045 | 1.0022 |
| scar_life | 0.239 | 14.57% | 1.0510 | **1.0255** |
| tally_lang | 0.025 | 1.00% | 1.0034 | 1.0017 |
| term_rank | 0.035 | 1.49% | 1.0050 | 1.0025 |
| ticket_audit | 0.023 | 0.64% | 1.0021 | 1.0011 |
| tree_fold | 0.107 | 2.87% | 1.0097 | 1.0048 |
| **pooled** | **0.997** | **3.24%** | **1.0109** | **1.0055** |

The runner-up `fastwalk.py` is smaller (0.858 s pooled, 2.79%; best 4.13% on tree_fold, halved
1.0070x). `ast` (CPython stdlib, 5.20% pooled, best 7.40% on tree_fold) halves to 1.0126x;
`connection` (stdlib IPC, 13.10% on tree_fold) halves to 1.0228x. No stdlib or compiler module
clears the gate.

The only module that clears it is `pyfunc.py`, which this job may not touch: 12.947 s pooled own
time (42.04% of cold wall; 24.57-64.23% per task), pooled 1.1630x full / 1.0815x halved, and
1.0446-1.1362x halved on 10/10 tasks. `pyfunc.py` is the codegen / bce-ranges / pyreach lane.

For the record, the whole-front-end ceiling is 1.141x full / 1.070x halved (60% of the front end
at 1.5x); a single module cannot reach it.

## 3. What was and was not run

- Setup: `~/scratch/mypyc-venv` (outside the repository) with Python 3.12.3 and **mypy 1.13.0**.
  Nothing was added to the repository's requirements. The `mypyc` entry point has no `--version`
  flag (it treats the argument as a module name and writes `build/setup.py`); the version was read
  from `mypy.version.__version__`. The generated `build/` directory was moved out of the tree to
  `/tmp/mypyc-artifacts/`.
- Not run, per the stop rule: `mypyc rangecheck.py`, `lab/mypyc/trial.py`, the 120-input C/refusal
  hash comparison, the 10-task instruction count, and the cold front-end seconds. Sub-step 2
  ("trial compile") is where the stop takes effect, so there is no measured "achieved" number and
  no `patch_rangecheck.diff`.
- Local tests on the final commit: `python3 tools/par_check.py -j 2 test_ail_safetynet
  test_ail_files test_ail_corpus_findings3` — **3 modules, 0 failed** (366 s).
  `python3 tools/update_manifest.py --check` passes. The change adds only markdown under
  `lab/mypyc/`, so no compiler test module was added or edited.
- CI shards: not run. The runner rule for this job is "commit on the current branch; do not push",
  so no PR/shard run exists for this change.

## 4. Recommendation for mypyc2

- **No-go for a single free-module pilot.** The best non-excluded module halves to 1.0255x on its
  best task and 1.0055x pooled; the whole job would be below the 1.03x floor.
- The only priced pilot is `pyfunc.py`: pooled 12.947 s own (42.04% of cold wall), 1.1630x full /
  1.0815x halved, >= 1.03x on 10/10 tasks. It needs the busy lane's coordination and its own mypyc
  feasibility trial (43.9k lines; `isinstance` dispatch over CPython `ast` objects), but it is the
  only single module whose price can pay.
- Keep the compiled `.so` out of the 0.1 wheel (owner decision 2026-11-05).

## 5. Data notes

- The per-task `rangecheck` seconds are `CTIME_FE.md` table 3/5 (serial view scaled to the as-run
  front end for the three worker tasks: tally_lang, ticket_audit, tree_fold). The raw
  `CTIME_FE.json` as-run module totals book those workers' bodies as pipe wait, so its
  `rangecheck` values for the three worker tasks are near zero; the serial view is the one
  `CTIME_FE.md` publishes and the brief says to take the share from there.
- `CTIME_FE` module rows are scaled cProfile tottime; tottime includes C builtins charged to the
  Python caller (20.3-28.6% of the front end). Leaving that C time out, as the brief asks, would
  lower every share and projection, so the stop is conservative.
- Pooled cold wall is the sum of table 1: 30.795 s. The 61.8% / 2.62x envelope is the separate
  `CTIME_2026-11.md` phase measurement (28.31 s of 45.82 s).
