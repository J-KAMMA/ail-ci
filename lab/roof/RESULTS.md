# roof: how close is each compare program to the hardware limit, and what limits it

Measurement only. Nothing in the compiler changed. Runner: GitHub Actions, 4 vCPU, shared with up
to five agents; the machine facts, the typed-source column and the C column were measured in the
same job with `bash lab/roof/run.sh`, and the task's `main.py` column was measured in the fix job on
the same runner type with `measure.py --langs ail-py` (the section below names it).

## The machine (measured here, not from a datasheet)

`lab/roof/clock.c`, `stream.c`, `chase.c`; raw output in `lab/roof/data/`.

| fact | value |
|---|---|
| CPU | AMD EPYC 7763 (Zen 3), 1 socket, 2 cores, 2 threads/core, 4 vCPU (Hyper-V) |
| caches | L1d 32 KiB/core, L2 512 KiB/core, L3 32 MiB (shared) |
| SIMD | SSE4.2, AVX, AVX2, FMA (no AVX-512) |
| clock (dependent `add` chain, latency 1) | **3.211 GHz** |
| scalar integer throughput (8 independent chains) | **2.67 adds/cycle** (4 ALUs nominal; the vCPU is SMT-shared) |
| AVX2 double throughput | 2.67 vector adds/cycle = **10.7 doubles/cycle** |
| spec peak, scalar, per core | 3.211 GHz x 4 IPC = **12.84 G ops/s** |
| STREAM triad (best median of 3, `data/stream_summary.txt`) | **46.38 GB/s** @1.5 MB, **46.05** @12 MB, **25.44** @96 MB, **25.10 GB/s** @402 MB (DRAM-resident) |
| random dependent load: L1 / L2 / L3 / DRAM | **5.1 / 18.8 / 54.9 / 374 cycles** (1.589 / 5.844 / 17.113 / 116.520 ns) |

The chasing load costs 116.5 ns on a DRAM miss, so a program that serialises its misses is capped at
8.6 M loads/s no matter how much bandwidth is idle. `%STREAM` below divides by the DRAM-resident
triad rate, **25.099 GB/s**.

## Two AIL sources (the fix from review 1)

The task names `lab/compare/src/<task>/main.py` as the AIL input. compare-lab reports two AIL
columns: `ail` builds `typed.py` (the annotated source) and `ail-py` builds `main.py` (the plain
CPython source). Review 1 found that the first version of this file measured only `typed.py`, so
the `boxed general path` verdict class was empty by construction. Both columns are now measured
and every row names its source. `main.py` is built with `--syntax python`; it also gets
`--exact-int` for `rail_transfer`, `chain_relax` (as compare-lab does) and for `scar_life`, whose
`# ail-build: --exact-int` directive asks for it (without it the binary builds but dies at runtime
with `OverflowError: ... --exact-int`, not a measurement).

Result: **the `main.py` column is a different machine.** Of the eight builds that compile, six are
on the general path and only `berth_sim` and `echo_pack` are typed; AIL's `main.py` build is
**1.6x-143x C's wall** (median 9.9x), not the 0.67x-1.98x the annotated source shows. Two programs
do not compile at all and are named refusals (below), not silent rows.

C: `gcc -O2 -std=c11`. AIL: `compile --syntax python` exactly as `lab/compare/run_task.py` builds
the `ail`/`ail-py` columns. In the typed-source table all ten builds took the typed path
(`--strict` accepted every one); in the task's `main.py` table that is true of `berth_sim` and
`echo_pack` only.

The vCPUs expose no hardware PMU (`/sys/bus/event_source/devices/` has no `cpu`), so `perf stat`,
`tools/icount.c` and `perf annotate` all fail: **instructions and LLC misses here come from
valgrind cachegrind** (3.22), configured with this runner's cache geometry, on the real perf input.
They are deterministic but simulated, not counted by hardware. Wall is the median of 3 native runs.
Cycles are estimated as wall x 3.211 GHz, so IPC is an estimate: `tally_lang` shows IPC 4.30, which
means the clock during that run was at least 3.45 GHz (the clock benchmark is a lower bound), or
Zen 3's 6-wide dispatch is retiring more than 4 instructions/cycle. Treat IPC as +-20%.

Cores used is measured, not assumed: `/usr/bin/time` reports user+sys CPU seconds and dividing by
wall gives the average busy cores (`data/cores.json`). Every program reads 0.98-1.00 except
`rail_transfer`, whose 0.07 s runtime is at the timer's resolution (0.80 AIL, 0.86 C); none creates
a thread.

Vectorisation is measured two ways (`lab/roof/vec.py`, `data/vec.json`): `gcc -fopt-info-vec-all`
on the emitted C for all ten programs in both AIL columns, and `objdump -d` of each emitted binary
counting instructions that touch an xmm/ymm register. The loop count answers "how much hot code is
vectorised" (none in the typed column; one loop in two `main.py` builds); the mnemonic share shows
the residual SIMD moves outside vectorised loops. For the five attributed programs the hot
functions' disassembly is in `data/attrib/attrib.json` (`hot_simd_share`).

## The task's source: `main.py` (compare-lab's `ail-py` column)

Wall is the median of 3 runs; counters are cachegrind (3.22), on the same input, `callgrind-sim`
where the cache simulation finished and `callgrind-ir` (instructions only, LLC `n/m`) where it
did not. `refused` means the compiler refused the source by name; `n/m` means the cachegrind run
exceeded the 20-minute cap (the general path executes so much more code that the simulation does
not finish in budget — the typed column's counters are given in the next table for comparison).
`%phys min` and IPC need instructions, so they are `n/m` there; `cycles*` is wall x 3.211 GHz and
is always available.

| task | source | wall s | instr | cycles* | IPC | LLC miss | GB/s | %STREAM | %peakIPC | vec loops | SIMD | cores | verdict | %phys min |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| berth_sim | main.py | 5.118 | 33.476e9 | 16.43e9 | 2.04 | 250.6M | 3.13 | 12% | 51% | 0 | 2.2% | 1.00 | compute-bound (scalar) | 51% |
| chain_relax | main.py | 153.767 | n/m | 493.7e9 | n/m | n/m | n/m | n/m | n/m | 0 | 13.8% | 1.00 | boxed general path | n/m |
| echo_pack | main.py | 5.770 | 18.231e9 | 18.53e9 | 0.98 | 36.4M | 0.40 | 2% | 25% | 0 | 0.8% | 1.00 | compute-bound (scalar) | 25% |
| ledger_bin | main.py | 48.847 | n/m | 156.8e9 | n/m | n/m | n/m | n/m | n/m | 0 | 18.7% | 1.00 | boxed general path | n/m |
| rail_transfer | main.py | 0.962 | 3.704e9 | 3.09e9 | 1.20 | 23.3M | 1.55 | 6% | 30% | 0 | 20.0% | 0.99 | boxed general path | 30% |
| scar_life | main.py | 30.904 | n/m | 99.2e9 | n/m | n/m | n/m | n/m | n/m | 1 | 23.9% | 1.00 | boxed general path | n/m |
| tally_lang | main.py | refused | - | - | - | - | - | - | - | - | - | - | build refused (regex pattern used as a value) | - |
| term_rank | main.py | 28.836 | 111.51e9 | 92.6e9 | 1.20 | n/m | n/m | n/m | 30% | 1 | 23.2% | 1.00 | boxed general path | 30% |
| ticket_audit | main.py | 56.998 | n/m | 183.0e9 | n/m | n/m | n/m | n/m | n/m | 0 | 25.3% | 1.00 | boxed general path | n/m |
| tree_fold | main.py | refused | - | - | - | - | - | - | - | - | - | - | build refused (compiled pattern used as a value; tuple element type) | - |

The two refusals are the compiler's own, unchanged by this lane:
`tally_lang/main.py:22` — "the compiled pattern TOK is used as a value"; `tree_fold/main.py:20` —
"the compiled pattern NODE is used as a value", then line 89 "cannot tell the type of element 0 of
this tuple". They are pre-existing build refusals (the same in the base tree), so they are reported
as refusals, not as measurements. For the eight builds that do compile, the `main.py` binary's
stdout and exit code on the perf input are byte-identical to the C build's (checked for all eight:
`/tmp/roofchk/equiv.py`).

### What the `main.py` table says

- **Compiling the plain source can cost 1-2 orders of magnitude.** `chain_relax` 153.8 s vs 1.263 s
  for the annotated source (122x; exact big ints on the general path), `ledger_bin` 48.8 s vs
  0.884 s (55x), `ticket_audit` 57.0 s vs 1.760 s (32x), `term_rank` 28.8 s vs 2.348 s (12x),
  `rail_transfer` 0.962 s vs 0.069 s (14x). Against C the eight builds that compile are 1.6x-143x
  (median 9.9x).
- **The annotated source is not a proxy.** `berth_sim` on `main.py` executes 33.5e9 instructions
  against 8.46e9 for `typed.py` (4.0x), `echo_pack` 18.2e9 vs 5.54e9 (3.3x), `rail_transfer`
  3.70e9 vs 0.391e9 (9.5x) — over the same inputs and with the same stdout. The two columns
  answer different questions: `typed.py` asks how fast the same algorithm can be if typed by hand;
  `main.py`, which the task asks for, measures what AIL does to ordinary Python.
- **The general path is the reason the verdict class was empty.** Six of the eight compiled builds
  (`chain_relax`, `ledger_bin`, `rail_transfer`, `scar_life`, `term_rank`, `ticket_audit`) are on
  the boxed general path. `scar_life` needs exact big ints (its bitmasks are wider than int64);
  without `--exact-int` the binary builds but exits at runtime with the compiler's named
  `OverflowError ... --exact-int`, so that flag is part of a correct build.
- **The typed `main.py` builds are not close to the roof either.** `berth_sim` is 51% of the
  4-IPC floor and 12% of STREAM; `echo_pack` 25% of the floor at IPC 0.98. Their limit is the
  emitted instruction stream, as in the typed table, not bandwidth.
- **A little vectorisation appears on the general path** (1 loop in `scar_life` and `term_rank`;
  SIMD share 13-25%, `ticket_audit` 25.3% with 0 vectorised loops), from list/bytes helper loops,
  not from the program's hot loop. The typed builds still have none.

## The annotated source table (`typed.py`, compare-lab's `ail` column)

`cycles*` = wall x 3.211 GHz. `GB/s` = LLC misses x 64 B / wall. `%STREAM` = GB/s / 25.099.
`%peakIPC` = IPC / 4. `vec loops` = loops the C compiler vectorised (`-fopt-info-vec-all`).
`SIMD` = share of the emitted binary's instructions that use an xmm/ymm register (residual moves,
not loop bodies). `cores` = measured CPU time / wall. `%phys min` = max(instructions / (4 x clock),
LLC bytes / STREAM triad) / wall; the dependent-load term from `chase.c` is not binding for any
program (all are array/queue based; see the verdicts). Values above 100% mean the 4-IPC model
understates the floor.

| task | lang | wall s | instr | cycles* | IPC | LLC miss | GB/s | %STREAM | %peakIPC | vec loops | SIMD | cores | verdict | %phys min |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| berth_sim | ail | 2.416 | 8.464e9 | 7.76e9 | 1.09 | 78.4M | 2.08 | 8% | 27% | 0 | 1.1% | 1.00 | latency-bound (pointer chasing) | 27% |
| berth_sim | c | 1.853 | 5.912e9 | 5.95e9 | 0.99 | 21.7M | 0.75 | 3% | 25% | 0 | - | 1.00 | latency-bound (pointer chasing) | 25% |
| chain_relax | ail | 1.263 | 1.693e9 | 4.06e9 | 0.42 | 0.0M | 0.00 | 0% | 10% | 0 | 3.6% | 0.99 | compute-bound (scalar) | 10% |
| chain_relax | c | 1.074 | 1.990e9 | 3.45e9 | 0.58 | 0.0M | 0.00 | 0% | 14% | 0 | - | 1.00 | compute-bound (scalar) | 14% |
| echo_pack | ail | 0.997 | 5.543e9 | 3.20e9 | 1.73 | 11.2M | 0.72 | 3% | 43% | 0 | 1.3% | 0.99 | compute-bound (scalar) | 43% |
| echo_pack | c | 0.630 | 1.924e9 | 2.02e9 | 0.95 | 3.4M | 0.34 | 1% | 24% | 0 | - | 0.98 | compute-bound (scalar) | 24% |
| ledger_bin | ail | 0.884 | 5.235e9 | 2.84e9 | 1.84 | 14.4M | 1.05 | 4% | 46% | 0 | 1.2% | 0.98 | compute-bound (scalar) | 46% |
| ledger_bin | c | 0.676 | 2.733e9 | 2.17e9 | 1.26 | 5.8M | 0.55 | 2% | 31% | 0 | - | 0.98 | compute-bound (scalar) | 31% |
| rail_transfer | ail | 0.069 | 0.391e9 | 0.22e9 | 1.76 | 0.5M | 0.45 | 2% | 44% | 0 | 1.4% | 0.80 | compute-bound (scalar) | 44% |
| rail_transfer | c | 0.103 | 0.308e9 | 0.33e9 | 0.93 | 0.4M | 0.27 | 1% | 23% | 0 | - | 0.86 | compute-bound (scalar) | 23% |
| scar_life | ail | 29.885 | n/m | 95.96e9 | - | n/m | - | - | - | 0 | 0.6% | 1.00 | memory-bound | - |
| scar_life | c | 19.109 | n/m | 61.36e9 | - | n/m | - | - | - | 0 | - | 1.00 | memory-bound | - |
| tally_lang | ail | 1.469 | 20.28e9 | 4.72e9 | 4.30 | 0.0M | 0.00 | 0% | 108% | 0 | 0.8% | 0.99 | compute-bound (scalar) | 108% |
| tally_lang | c | 1.159 | 11.90e9 | 3.72e9 | 3.20 | 0.0M | 0.00 | 0% | 80% | 0 | - | 0.99 | compute-bound (scalar) | 80% |
| term_rank | ail | 2.348 | 15.59e9 | 7.54e9 | 2.07 | 4.0M | 0.11 | 0% | 52% | 0 | 1.8% | 0.99 | compute-bound (scalar) | 52% |
| term_rank | c | 2.750 | 18.87e9 | 8.83e9 | 2.14 | 3.1M | 0.07 | 0% | 53% | 0 | - | 1.00 | compute-bound (scalar) | 53% |
| ticket_audit | ail | 1.760 | 13.00e9 | 5.65e9 | 2.30 | 10.7M | 0.39 | 2% | 58% | 0 | 2.8% | 0.99 | compute-bound (scalar) | 58% |
| ticket_audit | c | 0.888 | 2.406e9 | 2.85e9 | 0.84 | 7.3M | 0.53 | 2% | 21% | 0 | - | 0.99 | compute-bound (scalar) | 21% |
| tree_fold | ail | 1.408 | 9.053e9 | 4.52e9 | 2.00 | 106.1M | 4.82 | 19% | 50% | 0 | 3.1% | 0.99 | memory-bound | 50% |
| tree_fold | c | 0.977 | 4.446e9 | 3.14e9 | 1.42 | 20.0M | 1.31 | 5% | 35% | 0 | - | 0.99 | memory-bound | 35% |

`n/m`: `scar_life`'s cachegrind run is ~40x on this program (19 s native) and did not finish even
with the IR-only fallback; `measure.py` now falls through from the cache-simulated run to the
IR-only run and records `icount_method=timeout-ir` (`data/programs.json`). Its wall is measured
(median of 3: AIL 29.885 s, C 19.109 s) and the verdict is from the algorithm and wall ratio only.

### What the table says

- **In the typed column AIL is 0.67x-1.98x C's wall**; the sorted ratios are 0.67, 0.85, 1.18, 1.27, 1.30, 1.31, 1.44,
  1.56, 1.58, 1.98 (**median 1.31x**). Seven are between 1.0x and 1.6x, two are faster than C
  (`rail_transfer` 0.67x, `term_rank` 0.85x) and one is above 1.6x (`ticket_audit` 1.98x, which
  also executes 5.4x C's instructions; `echo_pack` is 1.58x wall and 2.9x instructions).
- **Nothing in the typed column is vectorised.** `-fopt-info-vec-all` on every emitted C: 0 loops vectorised and
  **35-139 "not vectorized" reports per program** (`scar_life` 35, `echo_pack` 47, `tally_lang` 51,
  `chain_relax` 53, `rail_transfer` 65, `ledger_bin` 68, `term_rank` 84, `berth_sim` 101,
  `ticket_audit` 133, `tree_fold` 139; `data/vec.json`). The residual SIMD mnemonics in the
  binaries are 0.6-3.6% of instructions (and 0.9-11.1% in the hottest functions of the attributed
  programs); they are scalar register moves (`pxor`, spills), not vectorised hot loops.
- **Only `tree_fold` is near a memory roof in the typed column** (19% of STREAM, 5.3x C's LLC
  misses). Every other typed program is below 9% of STREAM: they are not bandwidth-bound, they are
  issue/latency-bound.
- **`berth_sim` is latency-bound, not bandwidth-bound**: 78M LLC misses at only 2.08 GB/s means the
  misses are not overlapped; at 116.5 ns each a serial chain would need 9.1 s, so ~3-4 are in flight.
- **`tally_lang` and `chain_relax` have almost no memory traffic** and IPCs of 3.2-4.3 and 0.42: the
  former is a dense interpreter loop (close to the dispatch limit), the latter is bound by
  division/modulo and float formatting in `fmt`, not by instruction count.

## Subtraction: where the typed source's extra instructions go

Method (`lab/roof/attrib.py`): emit the C that AIL generates from `typed.py` (compare-lab's `ail`
column; the `main.py` general-path builds are too large to annotate in budget), rebuild it with `-g`
and the compiler's own flags, and run callgrind; do the identical line attribution on the C build's
`main.c`; then subtract line by line. `callgrind_annotate` gives Ir per emitted source line, so a
bounds check, an overflow check, a refcount update, an allocation, a copy or a box is read off the
line it was emitted for. Categories are line patterns; `other` is every line no pattern matched.
**Each column below is AIL minus C**, and the percentage is each category's share of the measured
AIL-C difference, so the shares sum to 100%.

The attribution build is not byte-identical to the real build (it adds `-g`,
`-fno-tree-slp-vectorize`, `-ffp-contract=off`, `-fopenmp-simd`), so its total difference is not
always the real instruction difference: `delta/real` is 0.99 for `echo_pack`, 1.09 for `ledger_bin`,
1.88 for `berth_sim` and 2.49 for `rail_transfer` (the C side's libc work is partly outside
`main.c`). The **shares** are the portable result; the absolute Ir is the attribution build's.

| task | AIL Ir | C Ir | AIL/C | d overflow | d bounds | d refcount | d alloc/free | d copies | d boxed | d other | real extra |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | 8.464e9 | 5.912e9 | 1.43 | 168.0M (3.5%) | 724.9M (15.1%) | 9.0M (0.2%) | 136.4M (2.8%) | 102.0M (2.1%) | 0 | 3.655e9 (76.2%) | 2.551e9 |
| chain_relax | 1.693e9 | 1.990e9 | 0.85 | 0 | 1.0K (0.0%) | 0.1K (0.0%) | 1.2K (0.0%) | 0.2K (0.0%) | 0 | 300.9M (100%) | -296.7M |
| echo_pack | 5.543e9 | 1.924e9 | 2.88 | 9.3M (0.3%) | 170.1M (4.8%) | 0.0M (0.0%) | 1.0M (0.0%) | 0.0M (0.0%) | 0 | 3.400e9 (95.0%) | 3.619e9 |
| ledger_bin | 5.235e9 | 2.733e9 | 1.92 | 796.5M (29.3%) | 222.0M (8.2%) | 1.9M (0.1%) | 15.4M (0.6%) | 5.1M (0.2%) | 0 | 1.674e9 (61.7%) | 2.502e9 |
| rail_transfer | 0.391e9 | 0.308e9 | 1.27 | 10.6M (5.2%) | 39.6M (19.2%) | 4.7M (2.3%) | 31.7M (15.4%) | 8.4M (4.1%) | 0 | 110.8M (53.8%) | 82.5M |

Five programs were attributed. The other five (`scar_life`, `tally_lang`, `term_rank`,
`ticket_audit`, `tree_fold`) are bounded by their AIL/C instruction ratios: `ticket_audit` 5.40x,
`tree_fold` 2.04x, `tally_lang` 1.70x, `term_rank` 0.83x, `scar_life` not counted (callgrind does
not finish). Coverage is 5 of 10, so the largest gaps (`ticket_audit` +10.6e9 Ir, `tally_lang`
+8.4e9) remain unattributed; what is known is that checks and allocation are not what makes them
5.4x and 1.7x.

Ranked by measured share of the extra (all five attributed programs):

1. **`other` (the shape of the emitted code): 54-100% of the extra** — 53.8% of `rail_transfer`,
   61.7% of `ledger_bin`, 76.2% of `berth_sim`, 95.0% of `echo_pack`, 100% of `chain_relax`. This is the AIL-minus-C
   difference in lines no check pattern matches: extra moves, reloads and one-statement-per-Python-
   operation temporaries. It is the largest term but it is not a removable check.
2. **Overflow/range checks: up to 29.3%** — `ledger_bin` 796.5M Ir (29.3% of its extra, 15.2% of
   all its instructions; Amdahl bound 1.18x), `rail_transfer` 5.2%, `berth_sim` 3.5%,
   `echo_pack` 0.3%. In `ledger_bin` the varint reader re-checks every accumulated digit against
   the int64 range; C does one comparison.
3. **Bounds/element access: 4.8-19.2%** — `rail_transfer` 39.6M (19.2% of its extra, 10.1% of its
   instructions, 1.11x), `berth_sim` 724.9M (15.1%, 8.6%, 1.09x), `ledger_bin` 222.0M (8.2%,
   4.2%, 1.04x), `echo_pack` 170.1M (4.8%, 3.1%, 1.03x).
4. **Allocation/free: up to 15.4%** — `rail_transfer` 31.7M (15.4% of its extra, 8.1% of its
   instructions, 1.09x); `berth_sim` 2.8% (sarena/list churn); negligible in `ledger_bin`.
5. **Copies: up to 4.1%** (`rail_transfer`), 2.1% `berth_sim`, 0.2% `ledger_bin`.
6. **Refcount: up to 2.3%** (`rail_transfer`), 0.2% `berth_sim`, 0.1% `ledger_bin`.
7. **Boxing: 0 in the attributed column** — all five attributed builds are `typed.py`. No
   `main.py` general-path build was attributed, so the boxing share of *that* column is measured
   only by its total (below); it is where the missing 8-143x must be.

## Ranked list: what would move how many programs, and by how much

"Programs moved" counts programs where the feature is worth >2% of wall. For items 2-9 the
speedup bound is Amdahl on the share of AIL's *own* instructions (the programs are
instruction-issue-bound, at 10-108% of the 4-IPC floor), not on the share of the extra. Item 1's
bound is the measured wall ratio between the two sources, not an Amdahl estimate.

1. **Land `main.py` on the typed path (remove the general path's boxing/refcounts) — the largest
   measured lever.** The task's source is general-path in six of eight compiled builds, and those
   builds are 1.6x-143x C while their `typed.py` counterparts are 0.67x-1.98x. The measured wall
   bound if the plain source reached the typed source's speed: `chain_relax` 153.8 s -> 1.263 s
   (**122x**), `ledger_bin` 48.8 -> 0.884 (**55x**), `ticket_audit` 57.0 -> 1.760 (**32x**),
   `rail_transfer` 0.962 -> 0.069 (**14x**), `term_rank` 28.8 -> 2.348 (**12x**), `scar_life`
   30.9 -> 29.9 (1.03x). Moves 6 programs, and is worth more than every hardware feature below
   combined. This is a compiler feature (typing/escape analysis over the plain source), not a
   hardware one.
2. **Cheaper emitted code / fewer temporaries for straight-line Python** (not a hardware feature,
   but the largest measured term within the typed column: 54-100% of the extra in the attributed
   programs). Would move
   `ticket_audit` (5.4x instructions, 1.98x wall), `echo_pack` (2.9x), `tree_fold` (2.0x),
   `ledger_bin` (1.9x), `tally_lang` (1.7x), `berth_sim` (1.4x). Bound: up to ~2x wall on
   `ticket_audit`. Needs better C emission (fewer temporaries, better aliasing information).
3. **Overflow checks with range facts (provable no-overflow / small int types)**: `ledger_bin`
   1.18x, `rail_transfer` 1.03x, `berth_sim` 1.02x — moves 3 measurably. Needs the int64 range
   analysis the compiler already has, applied to accumulators whose bound is provable, or
   `i32`/`u32` element types.
4. **Bounds checks from ownership/length proofs**: `rail_transfer` 1.11x, `berth_sim` 1.09x,
   `ledger_bin` 1.04x, `echo_pack` 1.03x — moves 4. The owner's "restrict from ownership proofs"
   idea is worth ~1.1x here, not more.
5. **Allocation reduction (arena/stack lists)**: `rail_transfer` 1.09x; `berth_sim` 1.02x. Moves 2.
6. **Copy and refcount elision**: `rail_transfer` 1.04x and 1.02x; `berth_sim` 1.02x and 1.00x.
   Moves 1-2 by >2%; small everywhere else.
7. **SIMD guarantees / "why not vectorised"**: **moves 0 programs today** — 0 vectorised loops in
   the typed builds, and the hot loops are data-dependent byte parsers. Worth doing for *messages*,
   not for speed on this suite.
8. **GIL-free `par for`, loop tiling, GPU offload**: all ten programs are single-threaded (measured
   0.98-1.00 cores) with <19% of STREAM and <1% of the machine's 4-core compute; they would need a
   different algorithm (parallel decomposition of a serial parser) before any of these pay. Not
   measurable as headroom here.
9. **Small int/float types**: no float hot loop exists (only `chain_relax`'s `fmt`); int64 is
   already the element type. No measured headroom.

The headline for the owner: **there are two answers, and the task's source is the one that matters.**
On `main.py` the physical minimum is not the limit at all: six of eight compiled builds are on the
boxed general path and run at 1.6x-143x C (median 9.9x; up to 122x the same program's annotated
source), so the first lever is getting ordinary Python onto the typed path, not any hardware
feature. On the annotated source (`typed.py`) all ten builds are typed and the physical minimum is
still not the limit — 0.67x-1.98x C, 10-108% of the 4-IPC floor, at most 19% of STREAM — so there
the instruction stream is the limit. Within the removable typed-path checks the measured order is
overflow (up to 29% of the extra) > bounds (up to 19%) > allocation (up to 15%) > copies (up to 4%)
> refcount (up to 2%); boxing is 0 there because every attributed build is typed, and boxing is
where the uncounted 8-143x of the `main.py` column lives.

## Files

- `lab/roof/clock.c`, `stream.c`, `chase.c` — the filter, measured in the same job.
- `lab/roof/run.sh`, `measure.py`, `attrib.py`, `vec.py`, `cores.py` — the harness.
- `lab/roof/data/` — raw microbenchmark output, `programs.json` (all counters for both AIL
  sources, including `scar_life`'s wall and the `n/m` rows), `vec.json` (both sources), `cores.json`,
  and `attrib/attrib.json` (per-category AIL and C line costs, the AIL-C delta, and hot-function
  disassembly).
- `measure.py` builds `typed.py` for `--langs ail` and `main.py` for `--langs ail-py`, honouring
  `--exact-int` for the tasks compare-lab names and for any source with an `# ail-build: --exact-int`
  directive. `--merge` keeps the other columns when one column is re-measured.
