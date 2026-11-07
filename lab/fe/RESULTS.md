# fe1 — where AIL's Python front end spends compile time

Measured 2026-11-07 with `lab/fe/prof.py` on branch `job-fe1-11071326` (the compiler is not changed). Python 3.12.3, `Linux-7.0.0-1017-azure-x86_64-with-glibc2.39`.
Sample: the ten `lab/compare/src/<task>/main.py`, their ten `typed.py`, and the twelve `corpus/gdev` programs timed in `lab/tcc/RESULTS.md` (`berth_sim` and `echo_pack` are already counted from `lab/compare`) — 32 programs in total, 30 that build here.

## Method

* Every build is cold: a fresh `AIL_CACHE`, a fresh `TMPDIR`, `AIL_NO_CACHE=1`, `AIL_SERVER=0`.
* Wall time is the median of `--reps` runs (see `reps` in the JSON; 3 here).
* The phase split comes from `timed_outer.py` / `timed_inner.py`, thin wrappers that start `ail_chatgpt.py` and `pyc.py` unchanged and add `perf_counter` around the driver's own top-level pass functions. Their `exclusive` time is non-overlapping; `other` is the remainder, and §1 shows that on the general path it is mostly the second `check` the driver runs to position its fallback note.
* `typed_emit` / `general_emit` are each reported whole: both emitters interleave type analysis with writing the C string (source line markers, temporaries, declarations), so splitting "analysis" from "C emission" would need a compiler change. The task's "C emission" row is therefore the emitter's exclusive time; "parse" is `ast.parse` from the cProfile runs.
* `cProfile` (a `sitecustomize.py` in both Python processes) is used for the pass-cumulative and top-20 tables. It inflates times 2–3x; the columns that matter for the Amdahl bounds in `docs/design/FRONTEND_SPEED.md` come from the low-overhead timed wrappers, not cProfile.
* `python3 -X importtime` is measured on each entry point; `/usr/bin/time -v` gives peak RSS.
* Peak RSS is the whole child tree (`ail_chatgpt.py` plus the `pyc.py` it starts), as reported by `/usr/bin/time -v` for the outer process.

## Fixed costs

| | seconds |
|---|---:|
| interpreter start + imports, outer driver (`ail_chatgpt.py`) | 0.0387 |
| interpreter start + imports, inner compiler (`pyc.py`) | 0.0812 |
| measured outer `import` (timed wrapper) | 0.0265 |
| measured inner `import` (timed wrapper) | 0.0690 |

`importtime` runs `--help`; the timed-wrapper `import` is the number used in the phase table.

## 1. Cold compile wall, split

Seconds. `pre` is the sum of the cheap refusal passes (`fold_int_constants`, `_refuse_static_big_calls`, `_python_defs_only_runs_nothing`, `_refuse_big_capable`, `_refuse_typed_big_store`). `typed`/`general` are the emitters.

| program | group | path | wall | start+import | load | pre | typed | general | C compile+link | other |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | compare-main | typed | 9.892 | 0.173 | 0.207 | 0.011 | 8.325 | 0.000 | 1.467 | 0.107 |
| berth_sim-typed | compare-typed | typed | 10.145 | 0.094 | 0.197 | 0.013 | 8.121 | 0.000 | 1.592 | 0.111 |
| chain_relax | compare-main | general | 7.001 | 0.093 | 0.083 | 0.014 | 0.000 | 1.991 | 4.287 | 0.340 |
| chain_relax-typed | compare-typed | typed | 2.195 | 0.120 | 0.120 | 0.009 | 1.438 | 0.000 | 0.559 | 0.098 |
| echo_pack | compare-main | typed | 2.192 | 0.095 | 0.173 | 0.010 | 1.024 | 0.000 | 0.763 | 0.102 |
| echo_pack-typed | compare-typed | typed | 3.768 | 0.095 | 0.191 | 0.012 | 2.911 | 0.000 | 0.523 | 0.096 |
| ledger_bin | compare-main | general | 16.098 | 0.097 | 0.206 | 0.013 | 0.330 | 6.781 | 7.773 | 0.833 |
| ledger_bin-typed | compare-typed | typed | 3.946 | 0.094 | 0.234 | 0.015 | 2.395 | 0.000 | 1.096 | 0.109 |
| rail_transfer | compare-main | general | 12.419 | 0.096 | 0.204 | 0.030 | 0.000 | 2.462 | 8.146 | 1.499 |
| rail_transfer-typed | compare-typed | typed | 3.556 | 0.098 | 0.336 | 0.020 | 1.574 | 0.000 | 1.381 | 0.111 |
| scar_life | compare-main | general | 97.381 | 0.097 | 1.706 | 0.119 | 6.133 | 61.336 | 15.488 | 10.938 |
| scar_life-typed | compare-typed | typed | 2.541 | 0.178 | 0.143 | 0.012 | 1.366 | 0.000 | 0.682 | 0.101 |
| tally_lang-typed | compare-typed | typed | 4.087 | 0.095 | 0.579 | 0.032 | 1.941 | 0.000 | 1.173 | 0.143 |
| term_rank | compare-main | general | 35.105 | 0.094 | 1.483 | 0.058 | 0.000 | 16.664 | 13.591 | 3.119 |
| term_rank-typed | compare-typed | typed | 3.579 | 0.094 | 0.218 | 0.013 | 1.630 | 0.000 | 1.412 | 0.102 |
| ticket_audit | compare-main | general | 94.416 | 0.099 | 1.835 | 0.161 | 18.548 | 17.241 | 34.071 | 23.801 |
| ticket_audit-typed | compare-typed | typed | 6.611 | 0.101 | 0.414 | 0.025 | 3.705 | 0.000 | 2.223 | 0.151 |
| tree_fold-typed | compare-typed | typed | 7.571 | 0.093 | 0.480 | 0.027 | 5.387 | 0.000 | 1.625 | 0.155 |
| g17_004 | tcc-corpus | general | 1.982 | 0.096 | 0.021 | 0.002 | 0.009 | 0.189 | 1.282 | 0.306 |
| g05_030 | tcc-corpus | general | 3.630 | 0.095 | 0.121 | 0.007 | 0.285 | 0.253 | 2.187 | 0.616 |
| g14_014 | tcc-corpus | general | 2.877 | 0.096 | 0.050 | 0.004 | 0.061 | 0.209 | 1.983 | 0.391 |
| g00_034 | tcc-corpus | typed | 10.017 | 0.097 | 1.111 | 0.078 | 5.750 | 0.000 | 2.815 | 0.236 |
| g18_008 | tcc-corpus | typed | 0.930 | 0.096 | 0.025 | 0.002 | 0.203 | 0.000 | 0.461 | 0.076 |
| g00_036 | tcc-corpus | typed | 0.556 | 0.095 | 0.027 | 0.002 | 0.110 | 0.000 | 0.159 | 0.075 |
| g04_006 | tcc-corpus | general | 3.411 | 0.095 | 0.069 | 0.004 | 0.208 | 0.209 | 2.180 | 0.560 |
| g14_004 | tcc-corpus | general | 2.165 | 0.095 | 0.024 | 0.002 | 0.068 | 0.143 | 1.391 | 0.373 |
| g19_028 | tcc-corpus | typed | 2.720 | 0.094 | 0.291 | 0.020 | 1.355 | 0.000 | 0.784 | 0.128 |
| g02_014 | tcc-corpus | general | 5.032 | 0.094 | 0.055 | 0.004 | 0.264 | 1.561 | 2.437 | 0.609 |
| g23_036 | tcc-corpus | general | 4.520 | 0.096 | 0.104 | 0.008 | 0.400 | 0.366 | 2.534 | 0.883 |
| g10_010 | tcc-corpus | general | 3.628 | 0.097 | 0.107 | 0.010 | 0.169 | 0.264 | 2.557 | 0.503 |

Refused / not built here: `tally_lang`, `tree_fold`.

### Typed and general path

| path | programs | median wall | median typed emit | median general emit | median C compile+link |
|---|---:|---:|---:|---:|---:|
| typed | 16 | 3.673 | 1.786 | 0.000 | 1.135 |
| general | 14 | 4.776 | 0.189 | 0.963 | 2.545 |

Total cold wall over the 30 programs that build: 363.97 s; of that the Python front end (`start+import` + `load` + `pre` + `typed` + `general`) is 197.98 s (54.4%), the C compiler and linker 118.62 s (32.6%).

### The doomed typed attempt on programs that fall back

For a program that ends on the general path, the front end first tries the typed emitter. `typed attempt` is its whole (failed) time; `general` is the path that produced the C.

| program | wall | typed attempt | general emit | typed share of wall |
|---|---:|---:|---:|---:|
| chain_relax | 7.001 | 0.000 | 1.991 | 0.0% |
| ledger_bin | 16.098 | 0.333 | 6.781 | 2.1% |
| rail_transfer | 12.419 | 0.000 | 2.462 | 0.0% |
| scar_life | 97.381 | 6.160 | 61.336 | 6.4% |
| term_rank | 35.105 | 0.000 | 16.664 | 0.0% |
| ticket_audit | 94.416 | 18.581 | 17.241 | 19.4% |
| g17_004 | 1.982 | 0.009 | 0.189 | 0.5% |
| g05_030 | 3.630 | 0.287 | 0.253 | 8.1% |
| g14_014 | 2.877 | 0.061 | 0.209 | 2.2% |
| g04_006 | 3.411 | 0.209 | 0.209 | 6.3% |
| g14_004 | 2.165 | 0.068 | 0.143 | 3.3% |
| g02_014 | 5.032 | 0.265 | 1.561 | 5.3% |
| g23_036 | 4.520 | 0.402 | 0.366 | 9.2% |
| g10_010 | 3.628 | 0.172 | 0.264 | 4.6% |

Across the general-path programs the failed typed attempt costs 26.55 s of 289.67 s wall (9.2%), and the general emitter 109.67 s (37.9%). 8 of the 14 general-path programs enter the typed emitter and then fall back (ledger_bin 0.33s, scar_life 6.16s, ticket_audit 18.58s, g05_030 0.29s, g04_006 0.21s, g02_014 0.26s, g23_036 0.40s, g10_010 0.17s); the rest are refused by a cheap pre-pass (`_refuse_big_capable` and friends) before the emitter runs, so their typed attempt is ~0.

### The `other` bucket is a second front end (`check` for the fallback note)

`other` is wall the timed wrappers do not cover. On the general-path programs it is not process spawn: `compile` ends by asking the driver to position its advisory `note: … built on the general path` line, and `_fallback_notes` → `_locate_refusal` (`ail_chatgpt.py:5499`, `:5995`) starts a second `ail_chatgpt.py check` over the whole source. That check runs the front end again; its cost lands in `other`, and it only happens when the program fell back, i.e. exactly on the slow builds. `AIL_QUIET_FALLBACK=1` avoids it (the note is advisory and its absence changes no stdout, stderr-by-default is the only difference).

| program | `other` s | share of that build |
|---|---:|---:|
| ticket_audit | 23.801 | 25.2% |
| scar_life | 10.938 | 11.2% |
| term_rank | 3.119 | 8.9% |
| rail_transfer | 1.499 | 12.1% |
| g23_036 | 0.883 | 19.5% |

Across all programs `other` is 46.67 s of 363.97 s (12.8%); on the five programs above it is 40.24 s.

### Pass boundaries (timed exclusive, cold, summed over all programs)

| pass | seconds | share of front end |
|---|---:|---:|
| `fold_int_constants` | 0.308 | 0.2% |
| `refuse_static_big_calls` | 0.182 | 0.1% |
| `python_defs_only_runs_nothing` | 0.080 | 0.0% |
| `refuse_big_capable` | 0.100 | 0.1% |
| `refuse_typed_big_store` | 0.064 | 0.0% |
| `typed_emit` | 73.855 | 37.3% |
| `general_emit` | 109.667 | 55.4% |
| `cc` | 118.761 | 32.6% |

`cc` is the C compile+link subprocess and is not part of the Python front end; it is listed for comparison. The cheap refusal passes cost about a second in total across 30 programs.

## 2. Top 20 functions by self time (cProfile, all programs)

Summed over every profiled cold build. cProfile overhead inflates these numbers; the ranking is what matters.

| # | function | file:line | self s | calls |
|---:|---|---|---:|---:|
| 1 | `walk` | `AIL_CURRENT/python/pkg-v12/fastwalk.py:24` | 93.770 | 81782995 |
| 2 | `iter_child_nodes` | `/usr/lib/python3.12/ast.py:269` | 24.823 | 53611441 |
| 3 | `_etype` | `AIL_CURRENT/python/pkg-v12/pyfunc.py:1640` | 24.385 | 445655 |
| 4 | `iter_fields` | `/usr/lib/python3.12/ast.py:257` | 14.748 | 80556837 |
| 5 | `analyze` | `AIL_CURRENT/python/pkg-v12/unified.py:973` | 12.915 | 41 |
| 6 | `_visit` | `AIL_CURRENT/python/pkg-v12/unified_lists.py:741` | 12.877 | 1639574 |
| 7 | `_walk_uncached` | `AIL_CURRENT/python/pkg-v12/pyfunc.py:43642` | 12.457 | 12467021 |
| 8 | `_etype` | `AIL_CURRENT/python/pkg-v12/unified.py:2098` | 11.748 | 4706600 |
| 9 | `_is_str_expr` | `AIL_CURRENT/python/pkg-v12/pyfunc.py:8696` | 11.533 | 963876 |
| 10 | `deepcopy` | `/usr/lib/python3.12/copy.py:118` | 11.263 | 27485 |
| 11 | `_format` | `/usr/lib/python3.12/ast.py:127` | 9.430 | 4661 |
| 12 | `find` | `AIL_CURRENT/python/pkg-v12/unified_lists.py:81` | 9.039 | 27333247 |
| 13 | `wrapper` | `AIL_CURRENT/python/pkg-v12/pyfunc.py:43567` | 8.186 | 997022 |
| 14 | `solve` | `AIL_CURRENT/python/pkg-v12/unified_lists.py:273` | 7.662 | 556 |
| 15 | `lists_round` | `AIL_CURRENT/python/pkg-v12/unified.py:1344` | 7.444 | 556 |
| 16 | `is_p` | `AIL_CURRENT/python/pkg-v12/unified_lists.py:48` | 5.201 | 19304161 |
| 17 | `stmt` | `AIL_CURRENT/python/pkg-v12/unified_lists.py:568` | 3.267 | 641074 |
| 18 | `_fix` | `/usr/lib/python3.12/ast.py:207` | 3.215 | 1410 |
| 19 | `stype` | `AIL_CURRENT/python/pkg-v12/unified_lists.py:496` | 2.664 | 2731684 |
| 20 | `_is_slist_expr` | `AIL_CURRENT/python/pkg-v12/pyfunc.py:7896` | 2.643 | 897062 |

## 3. Warm (whole-build cache hit)

A first run fills `AIL_CACHE`; the next runs hit the driver's `fe` entry and copy the stored binary. What still runs: the outer interpreter and its imports, `_load_sources` (reading and merging the source), the front-end key (hashing the merged source and every compiler source in `python/pkg-v12`), the cache lookup and unpack, and writing the output. `pyc.py` is not started, so `typed`/`general`/`cc` are 0. On a general-path program the hit ALSO runs the `check` subprocess that positions the advisory fallback note (the `other` column below and §1), so `scar_life` and `ticket_audit` stay at 12.3 s and 25.5 s warm: the whole-build cache does not remove that second front end.

| program | cold wall | fill run | warm wall | warm start+import | warm load | warm key hash | warm other |
|---|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | 9.892 | 10.018 | 0.365 | 0.026 | 0.212 | 0.066 | 0.070 |
| berth_sim-typed | 10.145 | 10.184 | 0.355 | 0.026 | 0.193 | 0.055 | 0.067 |
| chain_relax | 7.001 | 6.946 | 0.468 | 0.026 | 0.088 | 0.055 | 0.292 |
| chain_relax-typed | 2.195 | 2.310 | 0.261 | 0.027 | 0.101 | 0.053 | 0.066 |
| echo_pack | 2.192 | 2.221 | 0.334 | 0.027 | 0.176 | 0.055 | 0.067 |
| echo_pack-typed | 3.768 | 3.750 | 0.352 | 0.026 | 0.192 | 0.055 | 0.103 |
| ledger_bin | 16.098 | 16.113 | 1.062 | 0.026 | 0.209 | 0.055 | 0.774 |
| ledger_bin-typed | 3.946 | 4.004 | 0.394 | 0.026 | 0.234 | 0.055 | 0.068 |
| rail_transfer | 12.419 | 12.404 | 1.725 | 0.027 | 0.202 | 0.060 | 1.423 |
| rail_transfer-typed | 3.556 | 3.581 | 0.511 | 0.027 | 0.341 | 0.055 | 0.071 |
| scar_life | 97.381 | 96.700 | 12.323 | 0.026 | 1.677 | 0.064 | 10.566 |
| scar_life-typed | 2.541 | 2.588 | 0.301 | 0.026 | 0.143 | 0.055 | 0.067 |
| tally_lang-typed | 4.087 | 4.050 | 0.736 | 0.026 | 0.575 | 0.054 | 0.078 |
| term_rank | 35.105 | 34.874 | 4.493 | 0.026 | 1.488 | 0.056 | 2.937 |
| term_rank-typed | 3.579 | 3.676 | 0.378 | 0.026 | 0.216 | 0.055 | 0.067 |
| ticket_audit | 94.416 | 94.596 | 25.505 | 0.026 | 1.765 | 0.058 | 23.329 |
| ticket_audit-typed | 6.611 | 6.665 | 0.593 | 0.026 | 0.416 | 0.069 | 0.073 |
| tree_fold-typed | 7.571 | 7.679 | 0.645 | 0.026 | 0.480 | 0.055 | 0.077 |
| g17_004 | 1.982 | 2.008 | 0.382 | 0.027 | 0.021 | 0.054 | 0.268 |
| g05_030 | 3.630 | 3.657 | 0.779 | 0.027 | 0.121 | 0.055 | 0.561 |
| g14_014 | 2.877 | 2.931 | 0.501 | 0.026 | 0.050 | 0.055 | 0.350 |
| g00_034 | 10.017 | 9.996 | 1.277 | 0.027 | 1.082 | 0.054 | 0.101 |
| g18_008 | 0.930 | 0.979 | 0.181 | 0.027 | 0.025 | 0.054 | 0.062 |
| g00_036 | 0.556 | 0.584 | 0.182 | 0.027 | 0.028 | 0.055 | 0.061 |
| g04_006 | 3.411 | 3.427 | 0.700 | 0.027 | 0.070 | 0.054 | 0.518 |
| g14_004 | 2.165 | 2.209 | 0.448 | 0.026 | 0.025 | 0.055 | 0.330 |
| g19_028 | 2.720 | 2.753 | 0.467 | 0.025 | 0.294 | 0.054 | 0.080 |
| g02_014 | 5.032 | 5.044 | 0.701 | 0.026 | 0.056 | 0.062 | 0.546 |
| g23_036 | 4.520 | 4.505 | 1.022 | 0.026 | 0.103 | 0.054 | 0.827 |
| g10_010 | 3.628 | 3.694 | 0.628 | 0.025 | 0.104 | 0.054 | 0.429 |

Median over these programs: cold 3.86 s -> warm 0.51 s (7.6x). Excluding the two note-check outliers: cold 3.63 s -> warm 0.47 s (7.8x). The whole-build cache removes the front end; the fast residual is the outer process's load, hashing and binary copy.

## 4. Peak memory of the front end

`/usr/bin/time -v`, whole child tree, one cold build.

| program | path | peak RSS MiB | wall |
|---|---|---:|---:|
| berth_sim | typed | 81.2 | 9.884 |
| berth_sim-typed | typed | 83.4 | 10.141 |
| chain_relax | general | 152.6 | 6.942 |
| chain_relax-typed | typed | 48.9 | 2.193 |
| echo_pack | typed | 53.6 | 2.175 |
| echo_pack-typed | typed | 45.1 | 3.834 |
| ledger_bin | general | 236.8 | 16.003 |
| ledger_bin-typed | typed | 68.0 | 3.971 |
| rail_transfer | general | 245.0 | 12.367 |
| rail_transfer-typed | typed | 71.2 | 3.585 |
| scar_life | general | 363.0 | 121.397 |
| scar_life-typed | typed | 56.6 | 2.506 |
| tally_lang-typed | typed | 67.0 | 4.075 |
| term_rank | general | 348.4 | 37.100 |
| term_rank-typed | typed | 77.1 | 3.583 |
| ticket_audit | general | 526.7 | 95.093 |
| ticket_audit-typed | typed | 107.0 | 6.663 |
| tree_fold-typed | typed | 79.4 | 7.710 |
| g17_004 | general | 75.3 | 1.986 |
| g05_030 | general | 97.9 | 3.610 |
| g14_014 | general | 92.4 | 2.874 |
| g00_034 | typed | 105.3 | 10.056 |
| g18_008 | typed | 43.9 | 0.939 |
| g00_036 | typed | 40.2 | 0.551 |
| g04_006 | general | 98.9 | 3.392 |
| g14_004 | general | 78.1 | 2.152 |
| g19_028 | typed | 55.5 | 2.728 |
| g02_014 | general | 104.5 | 5.003 |
| g23_036 | general | 109.1 | 4.486 |
| g10_010 | general | 108.6 | 3.626 |

Median peak RSS 82.3 MiB, maximum 526.7 MiB (ticket_audit).

## Caveats

* The runner is shared. Absolute times move with load; ratios and shares are the stable part.
* `ast.parse` is called several times per build (driver merge, refusal passes, `_to_c`, `_rewrite_script`); cProfile attributes them all to `ast.parse`, which is why it appears in the top-20 rather than a single driver function.
* The emitter times include both analysis and C emission, as explained under Method.
