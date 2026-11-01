# Where AIL can beat C at equal effort: measurement and prices (2026-11-01)

Status: measurement and pricing only. **No compiler behaviour changed**; no file under
`AIL_CURRENT/` was edited, so the default build and its generated C are the same as at the base
commit.

Base: `staging:integ`, HEAD `5394a49` (`job-beatc1-11011753`). Machine: GitHub Actions runner,
4 logical x86-64 cores, 16 GB, gcc 13.3.0, CPython 3.12.3. Timings are from a runner that also
hosted up to five agents; medians are medians of 5 runs and `±` is **half the min-max range**, not
a standard deviation. A difference below 3% is called a tie.

Scripts and raw results are under `lab/beatc/`:

```sh
python3 lab/beatc/measure.py --runs 5 --out lab/beatc/results/baseline-5.json
python3 lab/beatc/profile.py --runs 4 --out lab/beatc/results/profile.json
python3 lab/beatc/step4.py   --runs 5 --out lab/beatc/results/step4.json
```

`measure.py` builds each task's unmodified `main.ail` with the default AIL build and its `main.c`
with `gcc -O2 -std=c11`; `profile.py` rebuilds the compiler's generated C with `-pg` and uses
`gprof`; `step4.py` edits only a `/tmp` copy of the generated C.

## 1. Baseline

One core is `taskset -c 0`; all cores is `taskset -c 0-3`. RSS is peak RSS from `/usr/bin/time -v`.
`AIL/C` is the one-core wall ratio; `C win` means C is faster by more than 3%.

| task | AIL 1c ms | C 1c ms | AIL/C | verdict | AIL all ms | C all ms | peak RSS MiB AIL / C |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| berth_sim | 2149.3 ± 24.1 | 1635.4 ± 32.2 | 1.31× | C win | 2147.1 | 1631.1 | 238.1 / 210.5 |
| chain_relax | 1120.7 ± 7.5 | 919.6 ± 3.0 | 1.22× | C win | 1117.7 | 919.9 | 3.9 / 4.4 |
| echo_pack | 818.8 ± 18.4 | 496.2 ± 5.9 | 1.65× | C win | 841.3 | 503.0 | 346.1 / 174.6 |
| ledger_bin | 750.4 ± 69.7 | 487.0 ± 5.3 | 1.54× | C win | 718.3 | 498.6 | 330.2 / 211.0 |
| rail_transfer | 880.0 ± 80.5 | 86.7 ± 103.5 | 10.15× | C win | 833.8 | 87.0 | 25.4 / 28.8 |
| scar_life | 24811.3 ± 586.5 | 16264.3 ± 474.0 | 1.53× | C win | 24795.6 | 16234.2 | 17.4 / 9.8 |
| tally_lang | 1269.5 ± 19.0 | 854.3 ± 27.3 | 1.49× | C win | 1267.6 | 852.1 | 1.9 / 1.9 |
| term_rank | 1843.0 ± 25.6 | 2393.3 ± 67.2 | 0.77× | **AIL win** | 1863.8 | 2407.1 | 157.9 / 164.4 |
| ticket_audit | 1711.9 ± 126.3 | 932.9 ± 37.8 | 1.84× | C win | 1641.8 | 951.8 | 248.8 / 268.0 |
| tree_fold | 1525.6 ± 20.0 | 897.5 ± 143.1 | 1.70× | C win | 1537.5 | 902.0 | 602.8 / 193.5 |

All ten AIL and C binaries produced the byte-identical reference output on the perf input
(`correct: true` for every task). AIL wins one task (`term_rank`, 1.30× faster than C); there are
no ties. The two biggest gaps are `rail_transfer` (10.15×, a Dijkstra/heap kernel heavily
optimised in the C version) and the memory gap on `tree_fold` (3.1× RSS).

**Instruction counts were not available.** `tools/icount.c` builds, but `perf_event_open` is
denied on this runner (`/proc/sys/kernel/perf_event_paranoid` is 4 and `sudo` is not permitted), and
there is no `valgrind`/callgrind binary. The JSON records `"instructions": null` and the reason.
No instruction-count claim is made anywhere below.

## 2. Profile of the nine non-AIL-winning tasks

`perf record` is denied for the same reason, so the fallback allowed by the task was used:
`gprof` on the compiler's generated C rebuilt with `-pg -g`, four runs per task on one pinned core.
Shares are SIGPROF samples; they are shares of sampled CPU time, not of a clean wall run, so they
are used only to rank hotspots.

| task | top functions | top loops / lines |
| --- | --- | --- |
| berth_sim | `py_main` 49.8%, `ail_slist_push` 40.9%, `ail_stdin_readline` 2.2% | `ail__keysort_i64` 31.9%; `py_main` key build 14.6%; `ck_mul` 11.1% |
| chain_relax | `py_main` 100% | `ail_fsqrt` 20.5% + 15.9% at two probes; `py_main` sweep 10.6%; `ail_fdiv` 7.2% |
| echo_pack | `pack` 93.2%, `ail_tab_hfree_slot` 2.6%, `flush` 1.1% | `ail_tab_hslot` 15.9% + 12.9% + 8.0%; `pack` 12.4%; `ail_bytes_get` 6.5% |
| ledger_bin | `py_main` 74.4%, `ail_keysort_perm.constprop` 12.4%, `readvar` 8.7% | `pymod` 26.2%; `ail_tab_hslot` 7.4% + 4.6%; two `py_main` lines 5.4% each |
| rail_transfer | `solve` 86.3%, `ail_rl_III_push` 6.2%, `py_main` 2.7% | `ail_rh_lt_III` 14.3%; `ail_rh_down_III` 9.7%; `ail_rl_III_push` 6.2% |
| scar_life | `py_main` 100% | cell-update lines 11.1%, 10.6%, 10.0%; `ck_add` 8.0% |
| tally_lang | `ev` 67.6%, `py_run__try1` 32.4% | `ev` 8.6%, `py_run__try1` 8.2%, `ev` 6.5% |
| ticket_audit | `py_main` 44.3%, `ail_stab_slot` 24.0%, `ail_sdict_put` 5.7% | `ail_stab_lookup` 18.5%; `ail_tab_hslot` 12.5% + 2.6%; `ck_add` 6.9% |
| tree_fold | `do_sort` 30.0%, `ail_slist_push` 16.4%, `rebuild` 15.2% | `ail_slist_push` 14.7%; `ail__key_i64_first` 6.0%; `ail__keysort_i64_first` 3.6% + 3.5% |

`term_rank` is the AIL win and was not profiled.

## 3. Price of each mechanism

`tools/roofcheck_v1.py` is **not present in this tree** (`find . -name 'roofcheck_v1.py'` returns
nothing), so no roofcheck run was possible. For A the only hardware roof used is the measured core
count, 4. For B, C and D the bound below is a *removal* bound, `1/(1-s)`, not a hardware roof: it
is what the task would gain if the mechanism removed all of the share `s` and changed nothing else.

The shares `s` are estimated from the line/function shares in section 2 plus the source; they are
rounded and deliberately conservative. AIL already specializes the int64 key sort and already
marks the generic hash probe `always_inline`, so C is charged only the generic remainder.

| task | A s | A 4-core bound | B s | B bound | C s | C bound | D s | D bound |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| berth_sim | 0.25 | 1.23× | 0.32 | 1.47× | 0.15 | 1.18× | 0.20 | 1.25× |
| chain_relax | 0.05 | 1.04× | 0.02 | 1.02× | 0.15 | 1.18× | 0.02 | 1.02× |
| echo_pack | 0.10 | 1.08× | 0.05 | 1.05× | 0.45 | 1.82× | 0.25 | 1.33× |
| ledger_bin | 0.15 | 1.13× | 0.15 | 1.18× | 0.30 | 1.43× | 0.20 | 1.25× |
| rail_transfer | 0.05 | 1.04× | 0.20 | 1.25× | 0.30 | 1.43× | 0.10 | 1.11× |
| scar_life | 0.50 | 1.60× | 0.10 | 1.11× | 0.15 | 1.18× | 0.10 | 1.11× |
| tally_lang | 0.00 | 1.00× | 0.02 | 1.02× | 0.65 | 2.86× | 0.02 | 1.02× |
| term_rank | 0.10 | 1.08× | 0.10 | 1.11× | 0.40 | 1.67× | 0.10 | 1.11× |
| ticket_audit | 0.10 | 1.08× | 0.20 | 1.25× | 0.35 | 1.54× | 0.10 | 1.11× |
| tree_fold | 0.30 | 1.29× | 0.35 | 1.54× | 0.30 | 1.43× | 0.35 | 1.54× |

Only three cells have a bound above the measured gap they would have to close: **A on
scar_life** (1.60× bound vs 1.53× needed), **B on berth_sim** (1.47× vs 1.31×) and **C on
echo_pack** (1.82× vs 1.65×). Every other cell is below the gap on its own. That is the central
result: most of the deficit is not in one removable phase.

Reachable fractions and why:

- **A, automatic parallelism: 60% of the 4-core bound on a large independent loop, 30% on a
  stateful loop.** The measured scar_life edit reached 1.40× median (1.45× paired) against a
  1.60× bound, i.e. about two thirds of the bound's excess; memory bandwidth, scheduling and the
  serial output phase take the rest. The other loops are dominated by stateful replay, a
  sequential heap/Dijkstra, or a hash table updated per item, so they are charged the lower 30%.
- **B, restrict: 25% of the removal bound.** The measured berth_sim edit reached 1.00–1.03×
  (a tie) against a 1.47× bound, so the realised fraction was near zero. GCC already gets many
  no-alias facts here because the sort helper is `static` and the arrays are separately allocated;
  `restrict` can only help the remaining vectorisation and `memcpy` cases, and it also changes
  nothing when the loop is a branchy merge.
- **C, specialization/inlining: 40% of the removal bound.** The big generic pieces are already
  specialized: `ail__keysort_i64` is a dedicated int64 merge sort and `ail_tab_hslot` is
  `static inline __attribute__((always_inline))`. What remains is the generic dict/bytes/compare
  tail and callbacks in the interpreter-like tasks. 40% allows for a better specialized string
  hash/bytes path and inlining, but assumes no algorithmic change.
- **D, arenas/regions: 50% of the removal bound.** An arena removes allocator metadata and
  `free` work, not the live working set; the C RSS is a floor, not zero. The tree_fold gap is
  603 MiB vs 194 MiB, so even a perfect lifetime grouping has to keep the live tree. 50% is the
  share of the allocation cost (not the whole RSS gap) assumed removable.

Realistic gains under those fractions are therefore about 1.36× for A on scar_life (close to the
1.40–1.45× measured), 1.33× for C on echo_pack, 1.27× for D on tree_fold and 1.12× for B on
berth_sim (measured 1.00–1.03×).

## 4. Cheap evidence: two hand-edited builds

Both builds are AIL's own generated C with the same `-O2` flags; the edit exists only under
`/tmp`. Base and edited runs were interleaved and their order alternated each round, so a loaded
patch of the shared runner hits both sides. `paired gain` is the median of the per-round
base/edited ratio; it is the number to trust when the load drifts.

| pair | byte-identical output | 1 core base → edited | 1 core gain | all cores base → edited | all cores gain (paired) | peak RSS base → edited |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A / scar_life: `#pragma omp parallel for reduction(+:alive,scars)` on the cell-update outer loop | **yes** | 24748.9 → 25309.4 ms | 0.978× (2.2% slower, tie) | 24822.7 → 17788.2 ms | **1.395× (paired 1.449×)** | 17.3 → 18.0 MiB |
| B / berth_sim: `restrict` on `perm`, `buf`, `key` in `AIL_KEYSORT_I64` | **yes** | 3136.8 → 3050.3 ms | 1.028× | 2934.6 → 2955.1 ms | 0.993× (paired 1.031×) | 238.9 → 238.9 MiB |

A / scar_life: the edited all-core runs were bimodal, 10.63, 10.89, 17.79, 20.74 and 20.95 s
(median 17.79 s, spread 10.32 s), because the runner was shared. The best edited run is 2.33×
faster than the base median and beats C's 16.23 s; the median is still 1.10× slower than C. The
one-core edited build is 2.2% slower, as expected from OpenMP bookkeeping. The output is
byte-identical (same SHA-256 as the reference on every run). This is real evidence for A but not
yet a win over C at the median.

B / berth_sim: the base and edited medians are 3136.8 and 3050.3 ms on one core and 2934.6 and
2955.1 ms on all cores; the paired all-core gain is 1.031×. Both are inside the 3% tie band, so
`restrict` produced **no measurable gain** on this already-specialized sort. The byte-identical
output confirms the `restrict` promise is true for these arrays, not that it pays.

Step 4 ran under heavier load than Step 1 (berth base 3.14 s here vs 2.15 s in section 1). Only
the paired ratios and the scar base, which matched its section-1 time, are used for conclusions.

## 5. Ranked list

1. **A — automatic parallelism.** Tasks: `scar_life` first; possibly `tree_fold` sort/fold and
   `berth_sim` key construction. Measured 1.40× all-core on scar_life (paired 1.45×, best 2.33×);
   priced 4-core bound 1.60×. Implementation: large, about 2–4k lines (dependence test, loop
   selection, OpenMP/task emission, scheduling, a serial fallback). Risk: float reduction order
   changes (`chain_relax` must not be parallelised), data races if the dependence test is wrong,
   output order, memory bandwidth. At the median it still does not beat C on scar_life.
2. **C — specialization and inlining.** Tasks: `echo_pack` (generic hash/bytes path, 45% share),
   then `ticket_audit`, `ledger_bin`, `rail_transfer`. Priced bound 1.82× on echo_pack, realistic
   about 1.33×; **not measured** in Step 4. Implementation: medium-large, about 1.5–3k lines
   (specialized dict/str/bytes routines, callback devirtualisation, controlled inlining). Risk:
   a specialized path that is subtly different from the generic one, code bloat and icache
   pressure; no float-order risk in these tasks.
3. **D — arenas/regions.** Tasks: `tree_fold` (RSS 3.1× C, 35% priced share), then `echo_pack`
   and `ledger_bin`. Priced speed bound 1.54× on tree_fold, realistic about 1.27× — below the
   1.70× speed gap, but the memory side is the real win (603 MiB toward C's 194 MiB).
   Implementation: large, about 2–4k lines (lifetime/escape analysis, region assignment, a
   fallback allocator). Risk: use-after-free and premature frees, a grouping bug that only shows
   on long inputs, peak RSS moving the wrong way.
4. **B — restrict.** Task: `berth_sim` (highest measured alias-sensitive share, 32%). Measured
   1.00–1.03× (tie), priced bound 1.47×. Implementation: small, about 150–400 lines (the alias
   facts are already known; the work is emitting them in the C and proving the promise). Risk:
   low if the analysis is right, but a wrong `restrict` is undefined behaviour; the measured
   payoff does not justify it before a broader alias study.

No single mechanism closes the measured AIL→C gap on its own at a realistic reach. A is the only
one with direct evidence of a large gain; C has the next best priced ceiling; D is primarily a
memory answer; B is a tie on the task with the most to gain from it.

## 6. Checks and limitations

- The ten tasks build with the default compiler; no `--strict`, no flag changes, no compiler
  patch. Generated C for all ten is the same as the base commit.
- Output was compared with each task's `reference.py` on the perf input for every measured run;
  all AIL and C runs were byte-identical. The Step-4 edited builds were also checked on every run.
- Wall time on this runner moves by up to about 30% between runs (see the spreads); all
  conclusions use medians, paired ratios, and the 3% tie rule.
- Instruction counts and `perf record` are unavailable on this runner; profiles are `gprof`
  samples and instructions are not claimed.
- `tools/roofcheck_v1.py` is absent, so the only roof used is the 4-core count for A; B/C/D are
  removal bounds, stated as such.
