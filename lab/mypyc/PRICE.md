# mypyc1: price of compiling one front-end module with mypyc

Measure-only. No compiler, runtime or test file was changed; this directory only. Base
`origin/integ` (fetched `f369daa`; the worktree is the export `73dedad`; `lab/profile/CTIME_FE.md`
and `.json` are byte-identical between the two). Sources: `lab/profile/CTIME_FE.md` / `.json`
(ctimes1, measured 2026-11-05) and `lab/profile/CTIME_2026-11.md` (measured 2026-11-04).

## 1. Measured envelope

- Summed cold wall over the 10 compare tasks: **45.82 s** (`CTIME_2026-11.md` table 1).
- Child front end: **28.31 s = 61.8%** pooled; Amdahl bound `1/(1 - 0.618) = 2.62x`.
- mypyc speeds only the module's own Python time. Time inside C code (`ast.parse`, `re`,
  `dict`/`list` builtins, `compile`) is not sped up and is left out of the price.
- The module rows in `CTIME_FE.md` are cProfile tottime scaled to the un-profiled child
  front-end wall. tottime includes C builtins charged to the Python caller (the charged share is
  20.3-28.6% of the front end, table 3), so the own-time shares below are **upper bounds**.
  Removing that C time lowers every projection; it cannot turn a stop into a go.

## 2. Formula and threshold

For a module with own-time share `s` of cold wall, with the assumed roof of **1.5x** (not mypy's
claimed 4x or Black's 2x: AIL walks CPython `ast` objects with `isinstance` dispatch, which mypyc
helps less than native classes):

```
full   = 1 / (1 - s * (1 - 1/1.5)) = 1 / (1 - s/3)
halved = 1 + (full - 1) / 2          # repo rule: halve every projected gain
```

A module clears 1.03x after halving only when `s/3 >= 1 - 1/(1 + 0.06)` on at least one task,
i.e. **s >= 17.0%** of the cold wall. The repo's earlier estimates overshot by 2-3x (2.5x
estimated / 0.88x measured; 1.83-1.92x estimated / 0.62-0.78x measured), which is why the gain is
halved.

## 3. Candidate modules

Own seconds are the `CTIME_FE.md` table 3/5 rows (serial view for the three worker tasks, scaled
to the as-run front end); per-task shares use table 1's cold wall. Excluded by the brief:
`pyfunc.py`, `optlib.py`, `cruntime.py`, `ir/passes/*`.

| module | owner | pooled own s | pooled share | best task share | best halved | clears 1.03? |
|---|---|---:|---:|---|---:|---|
| `pyfunc` | `pyfunc.py` (busy, **excluded**) | 12.947 | 42.04% | 64.23% echo_pack | 1.1362 | yes, 10/10 |
| `ast` | CPython stdlib | 1.600 | 5.20% | 7.40% tree_fold | 1.0126 | no |
| `rangecheck` | `rangecheck.py` | 0.997 | 3.24% | 14.57% scar_life | 1.0255 | no |
| `ir` group | `ir/ir.py` + `ir/passes/*` | 1.023 | 3.32% | 6.32% berth_sim | 1.0108 | no |
| `connection` | CPython stdlib (multiprocessing IPC) | 0.920 | 2.99% | 13.10% tree_fold | 1.0228 | no |
| `fastwalk` | `fastwalk.py` | 0.858 | 2.79% | 4.13% tree_fold | 1.0070 | no |
| `copy` | CPython stdlib | 0.686 | 2.23% | 2.87% berth_sim | 1.0048 | no |
| `other` (group) | many | 1.224 | 3.98% | 5.28% tree_fold | 1.0089 | no |

Notes:

- `optlib.py` and `cruntime.py` are below 0.01% in `CTIME_FE` and are excluded anyway.
- The `ir` group includes the excluded `ir/passes/*`; the free part is only `ir/ir.py`
  (`ir.walk`, 0.245 s pooled, 0.8% of cold wall).
- `ast`, `copy` and `connection` are CPython stdlib, not modules in the `AIL_CURRENT` export.
  They are shown only to make the gate robust: even if one were allowed, none clears 1.03x.
- No single module inside the `other` group exceeds 0.06 s pooled (`bigcap`).

## 4. Pick: `rangecheck.py`

`rangecheck.py` has the largest per-task own-time share of any non-excluded compiler module:
**0.997 s pooled (3.24%)** and **0.239 s on scar_life (14.57% of that task's cold wall)**.
`fastwalk.py` is second (0.858 s pooled, 2.79%; best 4.13% on tree_fold). The whole `ir` group's
pooled 3.32% is slightly above rangecheck's, but the group includes the excluded `ir/passes/*`;
its free module `ir/ir.py` is only 0.245 s pooled (0.8%), and the group's best task share (6.32%
on berth_sim) halves to 1.0108x. The choice does not change the gate.

| task | own s | share of cold wall | full | halved |
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

The best cell is scar_life 1.0255x; every task is below 1.03x.

## 5. The excluded module, for the mypyc2 decision

`pyfunc.py` is the only module that clears the gate. Table 3's serial-view own time is **12.947 s
pooled (42.04% of pooled cold wall; 24.57-64.23% per task)**. At the 1.5x roof and halved:
**pooled 1.1630x full / 1.0815x halved**, and 1.0446-1.1362x halved on all 10 tasks. It is
excluded here because `pyfunc.py` is a busy lane (codegen / bce-ranges / pyreach). This is the
only priced pilot for mypyc2; this job does not build it.

## 6. Whole-front-end ceiling (report only)

If 60% of the front end is own Python time and all of it reaches 1.5x, the build gets
`1/(1 - 0.618*0.6/3) = 1.141x` full, **1.070x halved**. The survey's -30..-45% assumes 2-4x on
the whole front end and is an upper bound, not a projection.

## 7. Decision

The brief's stop rule fires: every non-excluded module's halved projection is below 1.03x on
every task (best 1.0255x, `rangecheck` on scar_life). The only module above 1.03x is `pyfunc.py`,
which this job may not touch. The trial compile and the measurements are therefore not run;
`RESULTS.md` records the no-go.

## 8. Setup attempted

`~/scratch/mypyc-venv` (outside the repository) has Python 3.12.3 and **mypy 1.13.0**; nothing was
added to the repository's requirements. The `mypyc` entry point has no `--version` flag: it treats
`--version` as a module name and writes a `build/setup.py` in the current directory. The version is
therefore recorded from `mypy.version.__version__` (1.13.0); the generated `build/` directory was
moved to `/tmp/mypyc-artifacts/` and is not in the tree. No compile was run after the stop.
