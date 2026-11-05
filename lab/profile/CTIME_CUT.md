# ctimes2: price of the front-end cut, and stop decision

Base: `origin/integ` at the ctimes2 export (task commit `0e253de`).  Source of the price:
`lab/profile/CTIME_FE.md` on `origin/job-ctimes1-11051342` (`effbc50`).  No compiler file was
changed because the price below fires the brief's stop rule before any edit.

## 1. The pick ctimes1 named

`CTIME_FE.md` names **the `pyfunc` type/kind probes** (`_etype`, `_is_str_expr`, `_is_slist_expr`,
`type_of`, `_param_kinds`, `_map_kind`, ...) as the largest priced front-end cost:

| measure | value |
|---|---:|
| pooled own time, 10 compare tasks | 6.731 s |
| share of pooled cold wall (30.795 s in CTIME_FE) | 21.9% |
| full Amdahl bound | 1.280x |
| fraction of the bound assumed | 0.5 (repo halving rule) |
| halved projection (repo halving rule) | 1.123x |
| tasks where the halved projection is >= 1.10x | berth_sim 1.200, chain_relax 1.205, echo_pack 1.320, ledger_bin 1.108 |
| owner file | `AIL_CURRENT/python/pkg-v12/pyfunc.py` |
| lane | **busy** (codegen / bce-ranges / pyreach) |

`pyfunc.py` is explicitly excluded by this job, so this is written here as the follow-up for the
pyfunc lane, with the price above.  It is not built by ctimes2.

## 2. Best free row (the fallback the brief asks for)

`CTIME_FE.md` section 6 gives the two largest free-file rows.  `rangecheck.py` is the best free
row; `fastwalk.py:walk` is the best free row that is also in this job's editable list.  Both were
re-priced per task from the CTIME_FE seconds and wall, with the halving rule applied to the row's
own time (fraction of the full bound assumed: 0.5).

### `rangecheck.py` (range-check analysis)

| task | own s | share of cold wall | full bound | halved bound |
|---|---:|---:|---:|---:|
| berth_sim | 0.430 | 4.94% | 1.052 | 1.025 |
| chain_relax | 0.025 | 1.74% | 1.018 | 1.009 |
| echo_pack | 0.055 | 2.35% | 1.024 | 1.012 |
| ledger_bin | 0.030 | 1.23% | 1.012 | 1.006 |
| rail_transfer | 0.028 | 1.34% | 1.014 | 1.007 |
| scar_life | 0.239 | 14.56% | 1.170 | **1.079** |
| tally_lang | 0.025 | 1.00% | 1.010 | 1.005 |
| term_rank | 0.035 | 1.49% | 1.015 | 1.007 |
| ticket_audit | 0.023 | 0.64% | 1.006 | 1.003 |
| tree_fold | 0.107 | 2.87% | 1.030 | 1.015 |
| **pooled** | **0.997** | **3.2%** | **1.033** | **1.016** |

### `fastwalk.py:walk`

| task | own s | share of cold wall | full bound | halved bound |
|---|---:|---:|---:|---:|
| berth_sim | 0.186 | 2.14% | 1.022 | 1.011 |
| chain_relax | 0.025 | 1.74% | 1.018 | 1.009 |
| echo_pack | 0.027 | 1.16% | 1.012 | 1.006 |
| ledger_bin | 0.081 | 3.32% | 1.034 | 1.017 |
| rail_transfer | 0.062 | 2.98% | 1.031 | 1.015 |
| scar_life | 0.043 | 2.62% | 1.027 | 1.013 |
| tally_lang | 0.089 | 3.57% | 1.037 | 1.018 |
| term_rank | 0.073 | 3.11% | 1.032 | 1.016 |
| ticket_audit | 0.118 | 3.29% | 1.034 | 1.017 |
| tree_fold | 0.154 | 4.13% | 1.043 | **1.021** |
| **pooled** | **0.860** | **2.8%** | **1.029** | **1.014** |

Neither row reaches 1.10x at the halved projection on any task: the maximum halved bound is 1.079x
(rangecheck on scar_life) and 1.021x (fastwalk on tree_fold).  Only rangecheck's *full* bound on
scar_life clears 1.10x (1.170x), and that assumes the entire analysis becomes free.  `rangecheck.py`
is additionally outside this job's editable file list.  `fastwalk.py` is editable, but a cut there
cannot clear the target and would not be worth a byte-identity risk.

## 3. Earlier cuts, for calibration

From `CTIME_FE.md`: ctime walk reuse gave 1.15x on the front end; ctime1 took Python time
34.64 -> 20.54 s (1.69x); fepar2 gave 1.208x on the old-tree whole build with 4 workers.  The repo's
estimates have overshot by 2-3x before (2.5x estimated, 0.88x measured), so every projection here
is already halved.

## 4. Decision

The brief's pricing stop rule says: stop if the halved projection is below 1.10x on every task.
That is true for every free row.  The only pick that clears 1.10x on at least three tasks is the
`pyfunc` type/kind probe cache, and `pyfunc.py` is excluded by this job's file list.  The best
free row, `rangecheck.py`, is also outside the list; the best in-list free row, `fastwalk.py:walk`,
halves to at most 1.021x.  No byte-identical C change inside the permitted files can meet the
target, so ctimes2 makes **no compiler edit** and reports the price and the follow-up instead.

Follow-up for the pyfunc lane: memoise the pure type/kind predicates (`_etype`, `_is_str_expr`,
`_is_slist_expr`, `type_of`, `_param_kinds`, `_map_kind`) by AST node identity within one build.
Measured price: 6.731 s pooled, 21.9% of cold wall, full bound 1.280x, halved 1.123x; >= 1.10x on
berth_sim, chain_relax, echo_pack and ledger_bin.  It must keep every refusal message and the C
text order identical.
