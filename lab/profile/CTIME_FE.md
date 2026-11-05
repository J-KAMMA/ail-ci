# Cold front end by function, November 2026

Measured 2026-11-05 on a GitHub Actions runner (4 cores, Ubuntu 24.04, Python 3.12.3), base
`origin/integ`, with `python3 lab/profile/run.py --fe-profile --runs 3`.  Each cold build gets a
fresh `AIL_CACHE` and `TMPDIR` under `ulimit -v 1500000`; the child is `python3
AIL_CURRENT/python/pkg-v12/pyc.py` launched by `ail_chatgpt.py`.  All times are seconds, median of 3.

**Stop rule fired.**  The cProfile run and the plain run differ by more than 2x in child wall on
every task (table 1), so cProfile absolute seconds mislead.  Both are reported: the plain child
wall is used for every share and bound, and the profile is used only for relative function shape;
each function row is scaled to the un-profiled child front-end wall.  The `perf_counter` wrapper
run is within 0.92-1.31x of the plain child (median 1.01x), so its attempt times are usable.

A second profile with `AIL_FE_JOBS=1` was run for the four worker tasks: an in-parent cProfile
cannot see the forked workers, so without it their function bodies appear only as pipe wait
(`connection._recv`).  Function and candidate rows use that serial view for those four tasks;
the attribution table uses the as-run profile so its module rows add up to the real parallel FE.

## 1. Task summary

| task | cold wall | child Python | child FE (child - gcc - link) | serial FE | path | AIL_FE_JOBS workers | cProfile / plain child | top-25 own share | attributed |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| berth_sim | 6.383 | 6.077 | 4.917 | - | typed | 1 | 3.62x | 52.0% | 100.0% |
| chain_relax | 2.127 | 1.755 | 1.226 | - | typed | 1 | 3.58x | 56.5% | 100.0% |
| echo_pack | 2.858 | 2.570 | 1.988 | - | typed | 1 | 5.06x | 61.8% | 100.0% |
| ledger_bin | 3.602 | 3.167 | 2.342 | - | typed | 1 | 3.06x | 54.7% | 100.0% |
| rail_transfer | 2.245 | 1.905 | 0.970 | - | typed | 1 | 2.37x | 54.1% | 100.0% |
| scar_life | 1.778 | 1.491 | 0.981 | - | typed | 1 | 2.60x | 49.5% | 100.0% |
| tally_lang | 2.588 | 1.961 | 1.058 | 1.243 | typed | 4 | 2.54x | 52.5% | 100.0% |
| term_rank | 2.496 | 2.193 | 1.080 | - | typed | 1 | 2.36x | 53.3% | 100.0% |
| ticket_audit | 3.666 | 3.294 | 1.621 | 1.883 | typed | 4 | 2.50x | 54.4% | 100.0% |
| tree_fold | 3.865 | 3.468 | 2.208 | 2.239 | typed | 4 | 2.89x | 52.6% | 100.0% |
| **pooled** | **31.610** | **27.882** | **18.390** | | | | | | **100%** |

`attributed` is the share of the child front end carried by named function or module rows after
C functions are charged to their callers; it is 100% on all ten tasks.  `top-25 own share` is the
share carried by the 25 largest own-time functions alone; the rest is carried by the named module
groups in table 3, not by an unattributed remainder.

## 2. Path, fallback and wasted attempts

Every one of the ten tasks took the **typed** path.  There was no fallback note, no general-path
build and no pymix candidate: `wasted_s = 0` for all ten.  The first thing this job set out to
measure, time spent in a typed attempt or pymix candidate that was then thrown away, is **zero**
on the compare lab.  A `typed` attempt is the whole `pyfunc.to_c` time in table 4 (0.79-4.95 s per
task); it succeeded every time, so none of it was wasted.

`AIL_FE_JOBS` ran workers only where fepar2 expects them: 4 workers on tally_lang (22 functions),
ticket_audit (22) and tree_fold (18); serial on the other seven (4-7 functions, below the 8-function
threshold).  The real cost of the parallel path is visible in the as-run profile as
`connection._recv` (multiprocessing result transfer):

| task | workers | `connection._recv` s | share of child FE |
|---|---:|---:|---:|
| tally_lang | 4 | 0.108 | 10.2% |
| ticket_audit | 4 | 0.241 | 14.9% |
| tree_fold | 4 | 0.444 | 20.1% |

## 3. Attribution by task (as-run profile)

Seconds, with the share of that task's child FE in parentheses.  `ir` groups `ir/ir.py` and the
lowering/pass modules; `other` is every remaining named module (bigcap, boolkind, iterlower,
unbound, pyfront, callable_types, import bootstrap, ...).  Rows add to the child FE (rounding
accounts for the last 0.1%).

| task | pyfunc | ast | fastwalk | copy | rangecheck | connection | ir | other | total FE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | 3.334 (67.8%) | 0.289 (5.9%) | 0.129 (2.6%) | 0.162 (3.3%) | 0.333 (6.8%) | 0.000 (0.0%) | 0.485 (9.9%) | 0.184 (3.7%) | 4.916 |
| chain_relax | 0.979 (79.8%) | 0.052 (4.3%) | 0.033 (2.7%) | 0.017 (1.4%) | 0.034 (2.8%) | 0.000 (0.0%) | 0.042 (3.4%) | 0.068 (5.6%) | 1.225 |
| echo_pack | 1.660 (83.5%) | 0.055 (2.8%) | 0.029 (1.5%) | 0.024 (1.2%) | 0.060 (3.0%) | 0.000 (0.0%) | 0.051 (2.6%) | 0.108 (5.5%) | 1.988 |
| ledger_bin | 1.571 (67.1%) | 0.225 (9.6%) | 0.133 (5.7%) | 0.074 (3.2%) | 0.035 (1.5%) | 0.000 (0.0%) | 0.124 (5.3%) | 0.179 (7.6%) | 2.341 |
| rail_transfer | 0.624 (64.3%) | 0.108 (11.2%) | 0.064 (6.5%) | 0.039 (4.1%) | 0.029 (2.9%) | 0.000 (0.0%) | 0.011 (1.2%) | 0.095 (9.8%) | 0.969 |
| scar_life | 0.421 (42.9%) | 0.077 (7.9%) | 0.043 (4.4%) | 0.024 (2.4%) | 0.245 (24.9%) | 0.000 (0.0%) | 0.097 (9.8%) | 0.075 (7.6%) | 0.981 |
| tally_lang | 0.406 (38.4%) | 0.150 (14.2%) | 0.113 (10.6%) | 0.054 (5.1%) | 0.000 (0.0%) | 0.108 (10.2%) | 0.083 (7.8%) | 0.143 (13.5%) | 1.057 |
| term_rank | 0.667 (61.8%) | 0.124 (11.5%) | 0.072 (6.7%) | 0.049 (4.5%) | 0.036 (3.3%) | 0.000 (0.0%) | 0.028 (2.6%) | 0.104 (9.6%) | 1.079 |
| ticket_audit | 0.697 (43.0%) | 0.216 (13.3%) | 0.140 (8.6%) | 0.102 (6.3%) | 0.000 (0.0%) | 0.241 (14.9%) | 0.038 (2.4%) | 0.185 (11.4%) | 1.620 |
| tree_fold | 1.028 (46.6%) | 0.248 (11.3%) | 0.145 (6.6%) | 0.100 (4.5%) | 0.000 (0.0%) | 0.444 (20.1%) | 0.035 (1.6%) | 0.207 (9.4%) | 2.207 |

## 4. Top functions by own time (pooled over ten tasks, serial view)

Pooled own seconds.  C functions are charged to their Python callers, so `select.poll`/`posix.read`
are not rows.  `share` is of the pooled cold wall (31.610 s); `full` is the Amdahl bound if the row
became free, `halved` the bound if half of it is removed (the repo rule "halve every projection").

| function | module | owner file | own s | share | full bound | halved bound |
|---|---|---|---:|---:|---:|---:|
| `_etype` | pyfunc | pyfunc.py | 1.790 | 5.66% | 1.060 | 1.029 |
| `wrapper` | pyfunc | pyfunc.py | 0.921 | 2.91% | 1.030 | 1.015 |
| `walk` | fastwalk | fastwalk.py | 0.881 | 2.79% | 1.029 | 1.014 |
| `_is_str_expr` | pyfunc | pyfunc.py | 0.826 | 2.61% | 1.027 | 1.013 |
| `_walk_uncached` | pyfunc | pyfunc.py | 0.590 | 1.87% | 1.019 | 1.009 |
| `deepcopy` | copy | copy.py | 0.436 | 1.38% | 1.014 | 1.007 |
| `iter_child_nodes` | ast | ast.py | 0.435 | 1.38% | 1.014 | 1.007 |
| `iter_fields` | ast | ast.py | 0.370 | 1.17% | 1.012 | 1.006 |
| `_promote_floats` | pyfunc | pyfunc.py | 0.334 | 1.06% | 1.011 | 1.005 |
| `_bind_object_types` | pyfunc | pyfunc.py | 0.299 | 0.95% | 1.010 | 1.005 |
| `generic_visit` | ast | ast.py | 0.295 | 0.93% | 1.009 | 1.005 |
| `_is_slist_expr` | pyfunc | pyfunc.py | 0.284 | 0.90% | 1.009 | 1.005 |
| `_mark_str_containers` | pyfunc | pyfunc.py | 0.265 | 0.84% | 1.008 | 1.004 |
| `walk` | ir | ir.py | 0.249 | 0.79% | 1.008 | 1.004 |
| `_is_map_value` | pyfunc | pyfunc.py | 0.247 | 0.78% | 1.008 | 1.004 |
| `<genexpr>` | pyfunc | pyfunc.py | 0.214 | 0.68% | 1.007 | 1.003 |
| `_mark_tuple_lists` | pyfunc | pyfunc.py | 0.202 | 0.64% | 1.006 | 1.003 |
| `visit` | ast | ast.py | 0.178 | 0.56% | 1.006 | 1.003 |
| `_is_bytes_expr` | pyfunc | pyfunc.py | 0.173 | 0.55% | 1.005 | 1.003 |
| `_mark_bytes_containers` | pyfunc | pyfunc.py | 0.171 | 0.54% | 1.005 | 1.003 |
| `_is_owned_bytes_call` | pyfunc | pyfunc.py | 0.162 | 0.51% | 1.005 | 1.003 |
| `_param_kinds` | pyfunc | pyfunc.py | 0.147 | 0.46% | 1.005 | 1.002 |
| `_owned_method_name` | pyfunc | pyfunc.py | 0.137 | 0.43% | 1.004 | 1.002 |
| `_map_kind` | pyfunc | pyfunc.py | 0.134 | 0.42% | 1.004 | 1.002 |
| `_c_identifier_replace` | pyfunc | pyfunc.py | 0.131 | 0.42% | 1.004 | 1.002 |

The top 25 own rows carry 49.5-61.8% of each task's FE (table 1, column 9); `pyfunc` as a module
carries 38.4-83.5%, and the rest is in the named module groups of table 3.

## 5. Price of the cuts

Each row is a candidate cut, not a proposal to delete a function.  `seconds by task` is measured
own time in task order: berth_sim, chain_relax, echo_pack, ledger_bin, rail_transfer, scar_life,
tally_lang, term_rank, ticket_audit, tree_fold.  `share` and the bounds are pooled over the ten
tasks.  `halved` assumes the whole row is the roof and only half of it is removed (the repo's
halving rule); a row is marked "3-task" when that halved bound is at least 1.10x on at least three
tasks.  Files: **busy** = codegen/bce-ranges or pyreach lane (`pyfunc.py`), or `ir/passes/*`,
`optlib.py`, `cruntime.py`; **free** = not owned by a busy lane; **stdlib** = CPython, not editable
from this tree (the owner column then names the call site that would have to change).

| candidate (owner) | seconds by task | pooled s | share | full bound | halved bound | 3-task | owner file and function | lane |
|---|---|---:|---:|---:|---:|---|---|---|
| type/kind probes (`_etype`, `_is_*`, `type_of`, `_param_kinds`, ...) | 1.353, 0.492, 0.904, 0.535, 0.200, 0.123, 0.177, 0.201, 0.299, 0.390 | 4.674 | 14.8% | 1.174 | 1.080 | yes: berth_sim, chain_relax, echo_pack | `pyfunc.py` (`_etype`, `_is_str_expr`, `_is_slist_expr`, ...) | busy |
| `_etype` alone | 0.533, 0.193, 0.350, 0.203, 0.076, 0.046, 0.061, 0.081, 0.105, 0.142 | 1.790 | 5.7% | 1.060 | 1.029 | no | `pyfunc.py:_etype` | busy |
| analysis marker walks (`_mark_*`, `_promote_floats`, `_bind_object_types`) | 0.410, 0.055, 0.049, 0.279, 0.086, 0.066, 0.124, 0.107, 0.215, 0.261 | 1.653 | 5.2% | 1.055 | 1.027 | no | `pyfunc.py` (`_mark_str_containers`, `_promote_floats`, ...) | busy |
| `ast.iter_child_nodes` / `iter_fields` / `generic_visit` / `visit` | 0.257, 0.044, 0.046, 0.192, 0.092, 0.065, 0.141, 0.107, 0.213, 0.232 | 1.389 | 4.4% | 1.046 | 1.022 | no | `pyfunc.py` and `fastwalk.py` call sites (stdlib `ast.py`) | stdlib |
| `fastwalk.walk` | 0.129, 0.033, 0.029, 0.133, 0.064, 0.043, 0.101, 0.072, 0.136, 0.140 | 0.881 | 2.8% | 1.029 | 1.014 | no | `fastwalk.py:walk` | free |
| `pyfunc._walk_uncached` | 0.111, 0.018, 0.019, 0.088, 0.038, 0.027, 0.060, 0.048, 0.086, 0.095 | 0.590 | 1.9% | 1.019 | 1.009 | no | `pyfunc.py:_walk_uncached` | busy |
| `copy.deepcopy` of AST nodes | 0.162, 0.017, 0.024, 0.074, 0.039, 0.024, 0.062, 0.049, 0.106, 0.097 | 0.654 | 2.1% | 1.021 | 1.010 | no | `pyfunc.py` call sites (stdlib `copy.py`) | stdlib |
| `pyfunc.wrapper` | 0.264, 0.057, 0.111, 0.107, 0.059, 0.034, 0.047, 0.053, 0.081, 0.108 | 0.921 | 2.9% | 1.030 | 1.015 | no | `pyfunc.py:wrapper` | busy |
| range-check analysis | 0.333, 0.034, 0.060, 0.035, 0.028, 0.245, 0.029, 0.036, 0.026, 0.117 | 0.943 | 3.0% | 1.031 | 1.015 | no | `rangecheck.py` | free |
| IR walk/lowering (`ir.walk`, lower/pass modules) | 0.485, 0.042, 0.051, 0.124, 0.011, 0.097, 0.067, 0.028, 0.063, 0.054 | 1.021 | 3.2% | 1.033 | 1.016 | no | `ir/ir.py:walk`, `ir/passes/*` | free walk / busy passes |
| parallel result transfer (`_recv`) | 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.108, 0.000, 0.241, 0.444 | 0.793 | 2.5% | 1.026 | 1.013 | no | `pyfunc._fe_run_units` (stdlib multiprocessing) | stdlib |
| remaining pyfunc functions | 0.664, 0.164, 0.227, 0.360, 0.164, 0.125, 0.224, 0.177, 0.346, 0.389 | 2.840 | 9.0% | 1.099 | 1.047 | no | `pyfunc.py` | busy |
| wasted typed / pymix attempt | 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000 | 0.000 | 0.0% | 1.000 | 1.000 | no | none on the compare lab | - |

What earlier cuts achieved, for calibration: ctime walk reuse gave 1.15x on the front end; ctime1
took Python time 34.64 -> 20.54 s (1.69x); fepar2 gave 1.208x on the old-tree whole build with
4 workers.  The repo's estimates have overshot by 2-3x before (2.5x estimated, 0.88x measured),
so every projection here is halved.  The parallel row is the one that already exists and is already
paid: fepar2's 1.208x is what is left after the 0.108-0.444 s of pipe transfer visible here.

## 6. Pick for ctimes2

The best row anywhere is `pyfunc` type/kind probes (`_etype`, `_is_*`, `type_of`, `_param_kinds`,
`_map_kind`, ...): 4.674 s pooled, 14.8% of the pooled cold wall, full bound 1.174, halved bound 1.080.
That halved bound is at least 1.10x on three tasks (berth_sim 1.118, chain_relax 1.131,
echo_pack 1.188).  It is in `pyfunc.py`, which is owned by the codegen/bce-ranges and pyreach
lanes, so it is a **follow-up for that lane**, not a ctimes2 pick.

The largest free-file rows are `fastwalk.py:walk` (0.881 s pooled, 2.8% of wall, full bound 1.029,
halved 1.014; best task tally_lang 1.020) and `rangecheck.py` (0.943 s pooled, 3.0% of wall, full
bound 1.031, halved 1.015; best task scar_life 1.074).  Neither reaches 1.10x on any task, let alone
three, so **no free-file row meets the ctimes2 pick rule**.  `fastwalk`/`walkmemo` repeated-walk
reuse is the closest free idea (ctime already measured 1.15x on the front end), but the measured
`fastwalk` own time here is only 2.8% of the wall, and most of the repeated walk is charged to
`pyfunc._walk_uncached` (busy) and stdlib `ast`/`copy`, so it needs a pyfunc.py change to pay.

Recommendation: ctimes2 should not take a free-file cut on this lab.  The only row that clears
1.10x on three tasks is the pyfunc type/kind-probe cache, which belongs to the pyfunc lane; if that
lane is free, that is the pick.  The best genuinely free row, `rangecheck.py`, is a follow-up only
after a task where range-checking is large (scar_life, 24.9% of FE), and even there its halved
bound is 1.074x.

## 7. Files and method

`lab/profile/run.py --fe-profile` adds, without changing the default output: a `perf_counter`
wrapper run that records every `pyfunc.to_c` attempt (caller, entry, ok/refusal, seconds), every
`_fe_job_count`/`_fe_run_units` result, every `pyboxed2.build` and every `pymix.analyze`; and a
cProfile run of the same child.  It records the child argv, path, fallback note and worker count.
The C-function-time-to-caller rule is the one already used by `profile_phases`.  No compiler file
was changed.

The raw data (per-task top 25 by own and cumulative time, module totals, attempts, stop-rule
ratios) is `lab/profile/CTIME_FE.json`.
