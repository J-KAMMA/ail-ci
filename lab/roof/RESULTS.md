# roof: how close is each compare program to the hardware limit, and what limits it

Measurement only. Nothing in the compiler changed. Runner: GitHub Actions, 4 vCPU, shared with up
to five agents; every number below was measured in the same job, on the same runner, with
`bash lab/roof/run.sh`.

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

## Method and what is simulated

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
on the emitted C for all ten programs, and `objdump -d` of each emitted binary counting instructions
that touch an xmm/ymm register. The loop count answers "how much hot code is vectorised" (none);
the mnemonic share shows the residual SIMD moves outside vectorised loops. For the five attributed
programs the hot functions' disassembly is in `data/attrib/attrib.json` (`hot_simd_share`).

C: `gcc -O2 -std=c11`. AIL: `compile --syntax python` exactly as `lab/compare/run_task.py` builds
the `ail` column. **All ten AIL builds took the typed path** (`--strict` accepted every one), so
no row below is a boxed general-path build.

## The table

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

- **AIL is 0.67x-1.98x C's wall**; the sorted ratios are 0.67, 0.85, 1.18, 1.27, 1.30, 1.31, 1.44,
  1.56, 1.58, 1.98 (**median 1.31x**). Seven are between 1.0x and 1.6x, two are faster than C
  (`rail_transfer` 0.67x, `term_rank` 0.85x) and one is above 1.6x (`ticket_audit` 1.98x, which
  also executes 5.4x C's instructions; `echo_pack` is 1.58x wall and 2.9x instructions).
- **Nothing is vectorised.** `-fopt-info-vec-all` on every emitted C: 0 loops vectorised and
  **35-139 "not vectorized" reports per program** (`scar_life` 35, `echo_pack` 47, `tally_lang` 51,
  `chain_relax` 53, `rail_transfer` 65, `ledger_bin` 68, `term_rank` 84, `berth_sim` 101,
  `ticket_audit` 133, `tree_fold` 139; `data/vec.json`). The residual SIMD mnemonics in the
  binaries are 0.6-3.6% of instructions (and 0.9-11.1% in the hottest functions of the attributed
  programs); they are scalar register moves (`pxor`, spills), not vectorised hot loops.
- **Only `tree_fold` is near a memory roof** (19% of STREAM, 5.3x C's LLC misses). Every other
  program is below 9% of STREAM: they are not bandwidth-bound, they are issue/latency-bound.
- **`berth_sim` is latency-bound, not bandwidth-bound**: 78M LLC misses at only 2.08 GB/s means the
  misses are not overlapped; at 116.5 ns each a serial chain would need 9.1 s, so ~3-4 are in flight.
- **`tally_lang` and `chain_relax` have almost no memory traffic** and IPCs of 3.2-4.3 and 0.42: the
  former is a dense interpreter loop (close to the dispatch limit), the latter is bound by
  division/modulo and float formatting in `fmt`, not by instruction count.

## Subtraction: where AIL's extra instructions go

Method (`lab/roof/attrib.py`): emit the C that AIL generates (`--debug-dir`), rebuild it with `-g`
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

1. **`other` (the shape of the emitted code): 54-95% of the extra** — 53.8% of `rail_transfer`,
   61.7% of `ledger_bin`, 76.2% of `berth_sim`, 95.0% of `echo_pack`. This is the AIL-minus-C
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
7. **Boxing: 0 everywhere** — all five attributed builds are typed.

## Ranked list: what would move how many programs, and by how much

"Programs moved" counts programs where the feature is worth >2% of wall. The speedup bound is
Amdahl on the share of AIL's *own* instructions (the programs are instruction-issue-bound, at
10-108% of the 4-IPC floor), not on the share of the extra.

1. **Cheaper emitted code / fewer temporaries for straight-line Python** (not a hardware feature,
   but the largest measured term: 54-95% of the extra in the attributed programs). Would move
   `ticket_audit` (5.4x instructions, 1.98x wall), `echo_pack` (2.9x), `tree_fold` (2.0x),
   `ledger_bin` (1.9x), `tally_lang` (1.7x), `berth_sim` (1.4x). Bound: up to ~2x wall on
   `ticket_audit`. Needs better C emission (fewer temporaries, better aliasing information).
2. **Overflow checks with range facts (provable no-overflow / small int types)**: `ledger_bin`
   1.18x, `rail_transfer` 1.03x, `berth_sim` 1.02x — moves 3 measurably. Needs the int64 range
   analysis the compiler already has, applied to accumulators whose bound is provable, or
   `i32`/`u32` element types.
3. **Bounds checks from ownership/length proofs**: `rail_transfer` 1.11x, `berth_sim` 1.09x,
   `ledger_bin` 1.04x, `echo_pack` 1.03x — moves 4. The owner's "restrict from ownership proofs"
   idea is worth ~1.1x here, not more.
4. **Allocation reduction (arena/stack lists)**: `rail_transfer` 1.09x; `berth_sim` 1.02x. Moves 2.
5. **Copy and refcount elision**: `rail_transfer` 1.04x and 1.02x; `berth_sim` 1.02x and 1.00x.
   Moves 1-2 by >2%; small everywhere else.
6. **SIMD guarantees / "why not vectorised"**: **moves 0 programs today** — 0 vectorised loops in
   10/10, and the hot loops are data-dependent byte parsers. Worth doing for *messages*, not for
   speed on this suite.
7. **GIL-free `par for`, loop tiling, GPU offload**: all ten programs are single-threaded (measured
   0.98-1.00 cores) with <19% of STREAM and <1% of the machine's 4-core compute; they would need a
   different algorithm (parallel decomposition of a serial parser) before any of these pay. Not
   measurable as headroom here.
8. **Small int/float types**: no float hot loop exists (only `chain_relax`'s `fmt`); int64 is
   already the element type. No measured headroom.

The headline for the owner: **the physical minimum is not the limit for these programs — the
instruction stream is.** All ten run at 10-108% of the 4-IPC floor and at most 19% of STREAM. AIL
is faster than C on two programs and within 1.6x on five more; the one 2x outlier (`ticket_audit`)
executes 5.4x C's instructions. The largest measured lever is the emitted instruction count, and
within the removable checks the order is overflow (up to 29% of the extra) > bounds (up to 19%) >
allocation (up to 15%) > copies (up to 4%) > refcount (up to 2%); boxing is 0 because every build
is typed.

## Files

- `lab/roof/clock.c`, `stream.c`, `chase.c` — the filter, measured in the same job.
- `lab/roof/run.sh`, `measure.py`, `attrib.py`, `vec.py`, `cores.py` — the harness.
- `lab/roof/data/` — raw microbenchmark output, `programs.json` (all counters, including
  `scar_life`'s wall and `timeout-ir` marker), `vec.json`, `cores.json`, and
  `attrib/attrib.json` (per-category AIL and C line costs, the AIL-C delta, and hot-function
  disassembly).
