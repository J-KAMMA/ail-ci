# Cold front end by function, November 2026

Measured 2026-11-05 on a GitHub Actions runner (4 cores, Ubuntu 24.04, Python 3.12.3), base
`origin/integ`, with `python3 lab/profile/run.py --fe-profile --runs 3`.  Each cold build gets a
fresh `AIL_CACHE` and `TMPDIR` under `ulimit -v 1500000`; the child is `python3
AIL_CURRENT/python/pkg-v12/pyc.py` launched by `ail_chatgpt.py`.  All times are seconds.  Wall,
child and front-end times are medians of 3 plain builds; the attempt times are the final wrapped
run (its child wall is 0.99-1.18x the plain child, median 1.01x).  The driver's toolchain is
unchanged: gcc 13.3, `-O2`.

**Stop rule fired.**  The cProfile run and the plain run differ by more than 2x in child wall on
every task (table 1), so cProfile absolute seconds mislead.  Both are reported: the plain child
wall is used for every share and bound, and the profile is used only for relative function shape;
each function row is scaled to the un-profiled child front-end wall.

A second profile with `AIL_FE_JOBS=1` was run for the **three** worker tasks (`tally_lang`,
`ticket_audit`, `tree_fold`).  An in-parent cProfile cannot see the forked workers, so without it
their function bodies appear only as pipe wait (`connection._recv`).  Function and module rows use
that serial view for those three tasks, scaled to the as-run parallel front end (the brief allows
this); the as-run pipe wait is priced separately in table 2.

## Attribution: two independent measures

`attributed` (the done-check) is the cumulative time of the named front-end root `pyfunc.to_c`
over the gcc-free profiled front end.  It is read from cProfile's cumulative field, not summed
from the own-time rows, so a front end with work outside the named root would lower it; the
remainder is interpreter startup and imports.  `rows` is the separate partition of own time over
rows owned by named Python functions: C builtins are charged to their Python callers, and C
functions with no caller are the row residual.  Table 3 also splits the named total into time
executed directly by Python code and builtin time charged to a named caller, so the 90% claim does
not rest on the charging rule alone.  Pooled: attributed 18.790 s of 19.331 s (97.2%), rows 99.2%,
direct Python 74.3%, charged builtins 24.9%, orphan C 0.8%.

## 1. Task summary

| task | cold wall | child Python | child FE (child - gcc - link) | serial FE | path | AIL_FE_JOBS workers | cProfile / plain child | top-25 own share | attributed | rows |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| berth_sim | 8.702 | 8.460 | 7.286 | - | typed | 1 | 2.41x | 53.1% | 99.2% | 99.7% |
| chain_relax | 1.433 | 1.305 | 0.889 | - | typed | 1 | 3.15x | 56.7% | 96.3% | 98.6% |
| echo_pack | 2.337 | 2.196 | 1.800 | - | typed | 1 | 3.85x | 62.0% | 98.0% | 99.3% |
| ledger_bin | 2.437 | 2.249 | 1.439 | - | typed | 1 | 2.92x | 54.7% | 96.8% | 99.0% |
| rail_transfer | 2.084 | 1.876 | 0.946 | - | typed | 1 | 2.40x | 54.3% | 94.0% | 98.5% |
| scar_life | 1.641 | 1.484 | 0.974 | - | typed | 1 | 2.61x | 49.3% | 95.0% | 98.3% |
| tally_lang | 2.495 | 2.002 | 1.091 | 1.258 | typed | 4 | 2.58x | 52.7% | 93.7% | 98.7% |
| term_rank | 2.351 | 2.187 | 1.083 | - | typed | 1 | 2.35x | 53.4% | 95.8% | 98.6% |
| ticket_audit | 3.584 | 3.335 | 1.633 | 1.866 | typed | 4 | 2.51x | 54.5% | 96.6% | 99.2% |
| tree_fold | 3.731 | 3.458 | 2.190 | 2.229 | typed | 4 | 2.98x | 53.4% | 95.9% | 99.2% |
| **pooled** | **30.795** | **28.553** | **19.331** | | | | | | **97.2%** | **99.2%** |

Both attribution measures clear 90% on 10/10 tasks: the independent root measure is 93.7-99.2%
and the row partition is 98.3-99.7%.  The `top-25 own share` is the share carried by the 25
largest own-time functions alone; the rest is carried by the named module rows in table 3.

`berth_sim`'s plain child wall was unusually noisy this run (7.59-10.69 s across the three plain
builds, versus 6.02-6.17 s in the previous run on the same runner).  Every share and bound below
is computed within this run, so that noise inflates berth_sim's seconds but not the shapes.

## 2. Path, fallback and wasted attempts

Every one of the ten tasks took the **typed** path.  There was no fallback note, no general-path
build and no pymix candidate: `wasted_s = 0` for all ten.  The first thing this job set out to
measure, time spent in a typed attempt or pymix candidate that was then thrown away, is **zero**
on the compare lab.  A `typed` attempt is the whole `pyfunc.to_c` time below; it succeeded every
time, so none of it was wasted.

`AIL_FE_JOBS` ran workers only where fepar2 expects them: 4 workers on tally_lang (22 functions),
ticket_audit (22) and tree_fold (18); serial on the other seven (4-7 functions, below the
8-function threshold).  The real cost of the parallel path is visible only in the as-run profile
as `connection._recv` (multiprocessing result transfer):

| task | workers | functions | `to_c` s (wrapped) | `connection._recv` s | share of child FE |
|---|---:|---:|---:|---:|---:|
| tally_lang | 4 | 22 | 0.909 | 0.180 | 16.5% |
| ticket_audit | 4 | 22 | 1.357 | 0.251 | 15.4% |
| tree_fold | 4 | 18 | 2.008 | 0.489 | 22.3% |

## 3. Attribution by task (serial shape scaled to the as-run FE for the three worker tasks)

Seconds, with the share of that task's child FE in parentheses.  `ir` groups `ir/ir.py` and the
lowering/pass modules; `other` is every remaining named module (bigcap, boolkind, iterlower,
unbound, pyfront, callable_types, import bootstrap, ...).  Rows add to the child FE (rounding
accounts for the last 0.1%).  `direct` is the share of the FE executed directly by Python rows;
`charged` is builtin time charged to a named Python caller; the small remainder is orphan C.
The as-run pipe wait for the three worker tasks is in table 2; the serial shape has no pipe row.

| task | pyfunc | ast | fastwalk | copy | rangecheck | ir | other | total FE | direct | charged |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | 5.181 (71.1%) | 0.432 (5.9%) | 0.186 (2.6%) | 0.250 (3.4%) | 0.430 (5.9%) | 0.550 (7.5%) | 0.257 (3.5%) | 7.286 | 76.3% | 23.4% |
| chain_relax | 0.705 (79.3%) | 0.039 (4.4%) | 0.025 (2.8%) | 0.013 (1.4%) | 0.025 (2.8%) | 0.033 (3.7%) | 0.050 (5.6%) | 0.889 | 77.1% | 21.5% |
| echo_pack | 1.501 (83.4%) | 0.051 (2.9%) | 0.027 (1.5%) | 0.022 (1.2%) | 0.055 (3.1%) | 0.047 (2.6%) | 0.097 (5.4%) | 1.800 | 79.0% | 20.3% |
| ledger_bin | 0.962 (66.9%) | 0.135 (9.4%) | 0.082 (5.7%) | 0.043 (3.0%) | 0.030 (2.1%) | 0.083 (5.8%) | 0.105 (7.3%) | 1.439 | 73.6% | 25.4% |
| rail_transfer | 0.607 (64.2%) | 0.107 (11.3%) | 0.062 (6.6%) | 0.038 (4.1%) | 0.028 (2.9%) | 0.013 (1.3%) | 0.091 (9.6%) | 0.946 | 71.2% | 27.3% |
| scar_life | 0.420 (43.1%) | 0.077 (7.9%) | 0.043 (4.4%) | 0.023 (2.4%) | 0.239 (24.6%) | 0.098 (10.0%) | 0.074 (7.6%) | 0.974 | 73.1% | 25.2% |
| tally_lang | 0.613 (56.2%) | 0.145 (13.3%) | 0.089 (8.2%) | 0.054 (4.9%) | 0.025 (2.3%) | 0.061 (5.6%) | 0.104 (9.6%) | 1.091 | 70.7% | 28.1% |
| term_rank | 0.670 (61.8%) | 0.125 (11.5%) | 0.073 (6.7%) | 0.050 (4.6%) | 0.035 (3.3%) | 0.029 (2.7%) | 0.102 (9.4%) | 1.083 | 71.1% | 27.5% |
| ticket_audit | 0.981 (60.0%) | 0.213 (13.1%) | 0.118 (7.3%) | 0.093 (5.7%) | 0.023 (1.4%) | 0.059 (3.6%) | 0.147 (9.0%) | 1.633 | 70.5% | 28.6% |
| tree_fold | 1.307 (59.7%) | 0.276 (12.6%) | 0.154 (7.0%) | 0.100 (4.5%) | 0.107 (4.9%) | 0.050 (2.3%) | 0.197 (9.0%) | 2.190 | 70.9% | 28.2% |

The three worker tasks move the other way from the as-run profile: their `pyfunc` share is
56.2/60.0/59.7% in the serial view, not the 35.6/42.4/44.3% the parent-only profile shows,
because the parent profile books the workers' function time as `connection._recv`.

## 4. Top functions by own time (pooled over ten tasks, serial view)

Pooled own seconds.  C functions are charged to their Python callers, so `select.poll`/`posix.read`
are not rows.  `share` is of the pooled cold wall (30.795 s); `full` is the Amdahl bound if the row
became free, `halved` the bound if half of it is removed (the repo rule "halve every projection").

| function | module | owner file | own s | share | full bound | halved bound |
|---|---|---|---|---:|---:|---:|---:|
| `_etype` | pyfunc | pyfunc.py | 1.900 | 6.17% | 1.066 | 1.032 |
| `wrapper` | pyfunc | pyfunc.py | 0.970 | 3.15% | 1.033 | 1.016 |
| `_is_str_expr` | pyfunc | pyfunc.py | 0.890 | 2.89% | 1.030 | 1.015 |
| `walk` | fastwalk | fastwalk.py | 0.860 | 2.79% | 1.029 | 1.014 |
| `_walk_uncached` | pyfunc | pyfunc.py | 0.596 | 1.94% | 1.020 | 1.010 |
| `deepcopy` | copy | copy.py | 0.459 | 1.49% | 1.015 | 1.008 |
| `iter_child_nodes` | ast | ast.py | 0.431 | 1.40% | 1.014 | 1.007 |
| `iter_fields` | ast | ast.py | 0.362 | 1.18% | 1.012 | 1.006 |
| `_promote_floats` | pyfunc | pyfunc.py | 0.335 | 1.09% | 1.011 | 1.005 |
| `generic_visit` | ast | ast.py | 0.301 | 0.98% | 1.010 | 1.005 |
| `_is_slist_expr` | pyfunc | pyfunc.py | 0.300 | 0.98% | 1.010 | 1.005 |
| `_bind_object_types` | pyfunc | pyfunc.py | 0.295 | 0.96% | 1.010 | 1.005 |
| `_mark_str_containers` | pyfunc | pyfunc.py | 0.265 | 0.86% | 1.009 | 1.004 |
| `_is_map_value` | pyfunc | pyfunc.py | 0.262 | 0.85% | 1.009 | 1.004 |
| `walk` | ir | ir.py | 0.245 | 0.80% | 1.008 | 1.004 |
| `<genexpr>` | pyfunc | pyfunc.py | 0.216 | 0.70% | 1.007 | 1.004 |
| `_mark_tuple_lists` | pyfunc | pyfunc.py | 0.212 | 0.69% | 1.007 | 1.003 |
| `_is_bytes_expr` | pyfunc | pyfunc.py | 0.186 | 0.60% | 1.006 | 1.003 |
| `visit` | ast | ast.py | 0.180 | 0.58% | 1.006 | 1.003 |
| `_is_owned_bytes_call` | pyfunc | pyfunc.py | 0.173 | 0.56% | 1.006 | 1.003 |
| `_mark_bytes_containers` | pyfunc | pyfunc.py | 0.170 | 0.55% | 1.006 | 1.003 |
| `_c_identifier_replace` | pyfunc | pyfunc.py | 0.156 | 0.51% | 1.005 | 1.003 |
| `_param_kinds` | pyfunc | pyfunc.py | 0.149 | 0.48% | 1.005 | 1.002 |
| `_owned_method_name` | pyfunc | pyfunc.py | 0.145 | 0.47% | 1.005 | 1.002 |
| `_map_kind` | pyfunc | pyfunc.py | 0.141 | 0.46% | 1.005 | 1.002 |

The top 25 own rows carry 49.3-62.0% of each task's FE (table 1, column 9); `pyfunc` as a module
carries 43.1-83.4%, and the rest is in the named module groups of table 3.

## 5. Price of the cuts

Each row is a candidate cut, not a proposal to delete a function.  `seconds by task` is measured
own time in task order: berth_sim, chain_relax, echo_pack, ledger_bin, rail_transfer, scar_life,
tally_lang, term_rank, ticket_audit, tree_fold.  `share` and the bounds are pooled over the ten
tasks.  `halved` assumes the whole row is the roof and only half of it is removed (the repo's
halving rule); a row is marked with the tasks where that halved bound is at least 1.10x.  Files:
**busy** = codegen/bce-ranges or pyreach lane (`pyfunc.py`), or `ir/passes/*`, `optlib.py`,
`cruntime.py`; **free** = not owned by a busy lane; **stdlib** = CPython, not editable from this
tree (the owner column then names the call site that would have to change).  `_etype` alone is a
sub-row of the type/kind-probe row, not an additional cut.

| candidate (owner) | seconds by task | pooled s | share | full bound | halved bound | >=1.10x tasks | owner file and function | lane |
|---|---|---:|---:|---:|---:|---|---|---|
| type/kind probes (`_etype`, `_is_*`, `type_of`, `_param_kinds`, ...) | 2.895, 0.488, 1.133, 0.475, 0.263, 0.166, 0.206, 0.277, 0.343, 0.485 | 6.731 | 21.9% | 1.280 | 1.123 | berth_sim 1.200, chain_relax 1.205, echo_pack 1.320, ledger_bin 1.108 | `pyfunc.py` (`_etype`, `_is_str_expr`, `_is_slist_expr`, ...) | busy |
| `_etype` alone | 0.828, 0.140, 0.320, 0.135, 0.074, 0.046, 0.054, 0.081, 0.091, 0.131 | 1.900 | 6.2% | 1.066 | 1.032 | none | `pyfunc.py:_etype` | busy |
| analysis marker walks (`_mark_*`, `_promote_floats`, `_bind_object_types`) | 0.630, 0.038, 0.040, 0.146, 0.083, 0.066, 0.113, 0.108, 0.186, 0.246 | 1.657 | 5.4% | 1.057 | 1.028 | none | `pyfunc.py` (`_mark_str_containers`, `_promote_floats`, ...) | busy |
| `ast.iter_child_nodes` / `iter_fields` / `generic_visit` / `visit` | 0.350, 0.031, 0.040, 0.107, 0.084, 0.060, 0.114, 0.099, 0.170, 0.218 | 1.274 | 4.1% | 1.043 | 1.021 | none | `pyfunc.py` and `fastwalk.py` call sites (stdlib `ast.py`) | stdlib |
| `fastwalk.walk` | 0.186, 0.025, 0.027, 0.081, 0.062, 0.043, 0.089, 0.073, 0.118, 0.154 | 0.860 | 2.8% | 1.029 | 1.014 | none (best tree_fold 1.021) | `fastwalk.py:walk` | free |
| `pyfunc._walk_uncached` | 0.170, 0.013, 0.018, 0.052, 0.038, 0.026, 0.052, 0.048, 0.075, 0.104 | 0.596 | 1.9% | 1.020 | 1.010 | none | `pyfunc.py:_walk_uncached` | busy |
| `copy.deepcopy` of AST nodes | 0.169, 0.009, 0.015, 0.029, 0.025, 0.015, 0.036, 0.033, 0.061, 0.067 | 0.459 | 1.5% | 1.015 | 1.008 | none | `pyfunc.py` call sites (stdlib `copy.py`) | stdlib |
| `pyfunc.wrapper` | 0.410, 0.042, 0.095, 0.068, 0.057, 0.034, 0.041, 0.053, 0.070, 0.099 | 0.970 | 3.2% | 1.033 | 1.016 | none | `pyfunc.py:wrapper` | busy |
| range-check analysis | 0.430, 0.025, 0.055, 0.030, 0.028, 0.239, 0.025, 0.035, 0.023, 0.107 | 0.997 | 3.2% | 1.033 | 1.016 | none (best scar_life 1.079) | `rangecheck.py` | free |
| IR walk/lowering (`ir.walk`, lower/pass modules) | 0.550, 0.033, 0.047, 0.083, 0.013, 0.098, 0.061, 0.029, 0.059, 0.050 | 1.022 | 3.3% | 1.034 | 1.017 | none | `ir/ir.py:walk`, `ir/passes/*` | free walk / busy passes |
| parallel result transfer (`_recv`) | 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.180, 0.000, 0.251, 0.489 | 0.920 | 3.0% | 1.031 | 1.015 | none | `pyfunc._fe_run_units` (stdlib multiprocessing) | stdlib |
| remaining pyfunc functions | 1.075, 0.124, 0.214, 0.222, 0.165, 0.127, 0.201, 0.184, 0.306, 0.375 | 2.992 | 9.7% | 1.108 | 1.051 | none | `pyfunc.py` | busy |
| wasted typed / pymix attempt | 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000 | 0.000 | 0.0% | 1.000 | 1.000 | none | none on the compare lab | - |

What earlier cuts achieved, for calibration: ctime walk reuse gave 1.15x on the front end; ctime1
took Python time 34.64 -> 20.54 s (1.69x); fepar2 gave 1.208x on the old-tree whole build with
4 workers.  The repo's estimates have overshot by 2-3x before (2.5x estimated, 0.88x measured),
so every projection here is halved.  The parallel row is the one that already exists and is
already paid: fepar2's 1.208x is what is left after the 0.180-0.489 s of pipe transfer visible
here.

## 6. Pick for ctimes2

The best row anywhere is `pyfunc` type/kind probes (`_etype`, `_is_*`, `type_of`, `_param_kinds`,
`_map_kind`, ...): 6.731 s pooled, 21.9% of the pooled cold wall, full bound 1.280, halved bound
1.123.  That halved bound is at least 1.10x on four tasks (berth_sim 1.200, chain_relax 1.205,
echo_pack 1.320, ledger_bin 1.108).  It is in `pyfunc.py`, which is owned by the codegen/bce-ranges
and pyreach lanes, so it is a **follow-up for that lane**, not a ctimes2 pick.

The largest free-file rows are `rangecheck.py` (0.997 s pooled, 3.2% of wall, full bound 1.033,
halved 1.016; best task scar_life 1.079) and `fastwalk.py:walk` (0.860 s pooled, 2.8% of wall,
full bound 1.029, halved 1.014; best task tree_fold 1.021).  Neither reaches 1.10x on any task,
let alone three, so **no free-file row meets the ctimes2 pick rule**.  `fastwalk`/`walkmemo`
repeated-walk reuse is the closest free idea (ctime already measured 1.15x on the front end), but
the measured `fastwalk` own time here is only 2.8% of the wall, and most of the repeated walk is
charged to `pyfunc._walk_uncached` (busy) and stdlib `ast`/`copy`, so it needs a pyfunc.py change
to pay.

Recommendation: ctimes2 should not take a free-file cut on this lab.  The only row that clears
1.10x on three tasks is the pyfunc type/kind-probe cache, which belongs to the pyfunc lane; if that
lane is free, that is the pick.  The best genuinely free row, `rangecheck.py`, is a follow-up only
after a task where range-checking is large (scar_life, 24.6% of FE), and even there its halved
bound is 1.079x.

## 7. Files and method

`lab/profile/run.py --fe-profile` adds, without changing the default output: a `perf_counter`
wrapper run that records every `pyfunc.to_c` attempt (caller, entry, ok/refusal, seconds), every
`_fe_job_count`/`_fe_run_units` result, every `pyboxed2.build` and every `pymix.analyze`; and a
cProfile run of the same child.  It records the child argv, path, fallback note and worker count.
`profile_fe` measures attribution two independent ways: the named root's cumulative time over the
gcc-free profile (`attributed`), and the own-time partition over named Python rows with builtins
charged to callers (`rows`, split into `direct` and `charged`).  The C-function-time-to-caller
rule is the one already used by `profile_phases`.  No compiler file was changed.

The raw data (per task: top 25 by own and cumulative time, module totals, the two coverage
measures, attempts, stop-rule ratios) is `lab/profile/CTIME_FE.json`.
