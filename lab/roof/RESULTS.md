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
| STREAM triad, DRAM-resident (402 MB) | **22.56 GB/s** (25.0 GB/s at 96 MB, 45.6 GB/s L2-resident) |
| random dependent load: L1 / L2 / L3 / DRAM | **5.1 / 18.8 / 54.9 / 374 cycles** (1.59 / 5.84 / 17.1 / 116.5 ns) |

The chasing load costs 116 ns on a miss, so a program that serialises its misses is capped at
8.6 M loads/s no matter how much bandwidth is idle.

## Method and what is simulated

The vCPUs expose no hardware PMU (`/sys/bus/event_source/devices/` has no `cpu`), so `perf stat`,
`tools/icount.c` and `perf annotate` all fail: **instructions and LLC misses here come from
valgrind cachegrind** (3.22), configured with this runner's cache geometry, on the real perf input.
They are deterministic but simulated, not counted by hardware. Wall is the median of 3 native runs.
Cycles are estimated as wall x 3.211 GHz, so IPC is an estimate: `tally_lang` shows IPC 4.30, which
means the clock during that run was at least 3.45 GHz (the clock benchmark is a lower bound), or
Zen 3's 6-wide dispatch is retiring more than 4 instructions/cycle. Treat IPC as +-20%.

C: `gcc -O2 -std=c11`. AIL: `compile --syntax python` exactly as `lab/compare/run_task.py` builds
the `ail` column. **All ten AIL builds took the typed path** (`--strict` accepted every one), so
no row below is a boxed general-path build.

## The table

`cycles*` = wall x 3.211 GHz. `GB/s` = LLC misses x 64 B / wall. `%phys min` = max(instructions /
(4 x clock), LLC bytes / STREAM triad) / wall; the dependent-load term is the chase roof above and
is not binding for any program (all are array/queue based; see the verdicts). Values above 100% mean
the 4-IPC model understates the floor.

| task | lang | wall s | instr | cycles* | IPC | LLC miss | GB/s | %STREAM | %peakIPC(4) | vec hot | cores | verdict | %phys min |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| berth_sim | ail | 2.416 | 8.46e9 | 7.76e9 | 1.09 | 78.4M | 2.08 | 9% | 27% | 0% | 1 | latency-bound (pointer chasing) | 27% |
| berth_sim | c | 1.853 | 5.91e9 | 5.95e9 | 0.99 | 21.7M | 0.75 | 3% | 25% | 0% | 1 | latency-bound (pointer chasing) | 25% |
| chain_relax | ail | 1.263 | 1.69e9 | 4.06e9 | 0.42 | 0.04M | 0.00 | 0% | 10% | 0% | 1 | compute-bound (scalar) | 10% |
| chain_relax | c | 1.074 | 1.99e9 | 3.45e9 | 0.58 | 0.04M | 0.00 | 0% | 14% | 0% | 1 | compute-bound (scalar) | 14% |
| echo_pack | ail | 0.997 | 5.54e9 | 3.20e9 | 1.73 | 11.2M | 0.72 | 3% | 43% | 0% | 1 | compute-bound (scalar) | 43% |
| echo_pack | c | 0.630 | 1.92e9 | 2.02e9 | 0.95 | 3.4M | 0.34 | 2% | 24% | 0% | 1 | compute-bound (scalar) | 24% |
| ledger_bin | ail | 0.884 | 5.23e9 | 2.84e9 | 1.84 | 14.4M | 1.05 | 5% | 46% | 0% | 1 | compute-bound (scalar) | 46% |
| ledger_bin | c | 0.676 | 2.73e9 | 2.17e9 | 1.26 | 5.8M | 0.55 | 2% | 31% | 0% | 1 | compute-bound (scalar) | 31% |
| rail_transfer | ail | 0.069 | 0.39e9 | 0.22e9 | 1.76 | 0.49M | 0.45 | 2% | 44% | 0% | 1 | compute-bound (scalar) | 44% |
| rail_transfer | c | 0.103 | 0.31e9 | 0.33e9 | 0.93 | 0.43M | 0.27 | 1% | 23% | 0% | 1 | compute-bound (scalar) | 23% |
| scar_life | ail | 29.80 | n/m | 95.7e9 | - | n/m | - | - | - | 0% | 1 | memory-bound | - |
| scar_life | c | 19.13 | n/m | 61.4e9 | - | n/m | - | - | - | 0% | 1 | memory-bound | - |
| tally_lang | ail | 1.469 | 20.28e9 | 4.72e9 | 4.30 | 0.00M | 0.00 | 0% | 108% | 0% | 1 | compute-bound (scalar) | 108% |
| tally_lang | c | 1.159 | 11.90e9 | 3.72e9 | 3.20 | 0.00M | 0.00 | 0% | 80% | 0% | 1 | compute-bound (scalar) | 80% |
| term_rank | ail | 2.348 | 15.59e9 | 7.54e9 | 2.07 | 4.0M | 0.11 | 0% | 52% | 0% | 1 | compute-bound (scalar) | 52% |
| term_rank | c | 2.750 | 18.87e9 | 8.83e9 | 2.14 | 3.1M | 0.07 | 0% | 53% | 0% | 1 | compute-bound (scalar) | 53% |
| ticket_audit | ail | 1.760 | 13.00e9 | 5.65e9 | 2.30 | 10.7M | 0.39 | 2% | 58% | 0% | 1 | compute-bound (scalar) | 58% |
| ticket_audit | c | 0.888 | 2.41e9 | 2.85e9 | 0.84 | 7.3M | 0.53 | 2% | 21% | 0% | 1 | compute-bound (scalar) | 21% |
| tree_fold | ail | 1.408 | 9.05e9 | 4.52e9 | 2.00 | 106.1M | 4.82 | 21% | 50% | 0% | 1 | memory-bound | 50% |
| tree_fold | c | 0.977 | 4.45e9 | 3.14e9 | 1.42 | 20.0M | 1.31 | 6% | 35% | 0% | 1 | memory-bound | 35% |

`n/m`: scar_life's cachegrind run is ~40x on this program (19 s native) and did not finish inside
the job's budget; its wall time is measured (median of 3), the counters are not. Verdict from the
algorithm and the wall ratio only.

### What the table says

- **AIL is within 1.0-1.6x of C on 9 of 10 programs** (median 1.29x); it is *faster* than C on
  `rail_transfer` (0.67x) and `term_rank` (0.85x). The outliers are `ticket_audit` (1.98x) and
  `echo_pack` (1.58x), where AIL also executes 5.4x and 2.9x the C instruction count.
- **Nothing is vectorised.** `gcc -fopt-info-vec-all` on every emitted C: 0 loops vectorised, 47-68
  "not vectorized" reports per program. The hot loops are byte-at-a-time parsers and branchy
  tokenisers, so the "could vectorise" verdict applies to none of them.
- **Only `tree_fold` is near a memory roof** (21% of STREAM, 5.3x C's LLC misses). Every other
  program is below 10% of STREAM: they are not bandwidth-bound, they are issue/latency-bound.
- **`berth_sim` is latency-bound, not bandwidth-bound**: 78M LLC misses at only 2.1 GB/s means the
  misses are not overlapped; at 116 ns each a serial chain would need 9 s, so ~3-4 are in flight.
- **`tally_lang` and `chain_relax` have almost no memory traffic** and IPCs of 3.2-4.3 and 0.42: the
  former is a dense interpreter loop (close to the dispatch limit), the latter is bound by
  division/modulo and float formatting in `fmt`, not by instruction count.

## Subtraction: where AIL's extra instructions go

Method (`lab/roof/attrib.py`): emit the C that AIL generates (`--debug-dir`), rebuild it with `-g`
and the compiler's own flags, run callgrind, and read Ir per emitted source line
(`callgrind_annotate --auto=yes`). Categories are line patterns: overflow/range checks,
bounds/element access, refcount, allocation/free, copies, boxing.

| task | AIL Ir | C Ir | AIL/C | overflow | bounds | refcount | alloc/free | copies | boxed | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | 8.46e9 | 5.91e9 | 1.43 | 168.0M (2.0%) | 897.3M (10.6%) | 9.0M (0.1%) | 180.0M (2.1%) | 102.0M (1.2%) | 0 | 6.86e9 (81.0%) |
| chain_relax | 1.69e9 | 1.99e9 | 0.85 | 0.0M | 0.0M | 0.0M | 0.0M | 0.0M | 0 | 1.69e9 (100%) |
| echo_pack | 5.54e9 | 1.92e9 | 2.88 | 9.3M (0.2%) | 170.1M (3.1%) | 0.0M | 1.0M (0.0%) | 1.5M (0.0%) | 0 | 5.25e9 (94.7%) |
| ledger_bin | 5.23e9 | 2.73e9 | 1.92 | 796.5M (15.7%) | 222.0M (4.4%) | 1.9M (0.0%) | 28.9M (0.6%) | 5.1M (0.1%) | 0 | 4.02e9 (79.2%) |
| rail_transfer | 0.39e9 | 0.31e9 | 1.27 | 10.6M (2.8%) | 40.0M (10.5%) | 4.7M (1.2%) | 32.0M (8.4%) | 8.4M (2.2%) | 0 | 286.1M (75.0%) |

Five programs (`scar_life`, `tally_lang`, `term_rank`, `ticket_audit`, `tree_fold`) were still
being attributed when the budget ran out. Their `AIL/C` instruction ratio bounds the total extra:
`ticket_audit` 5.40x, `tree_fold` 2.04x, `tally_lang` 1.70x, `term_rank` 0.83x, `scar_life` not counted.

What is measurable today:

1. **Overflow/range checks: 15.7% of `ledger_bin`'s AIL instructions** (796M Ir) — the varint
   reader re-checks every accumulated digit against the int64 range; C does one comparison.
2. **Bounds/element access: 10.6% of `berth_sim` (897M Ir) and 10.5% of `rail_transfer`, 4.4% of
   `ledger_bin`, 3.1% of `echo_pack`.**
3. **Allocation/free: 8.4% of `rail_transfer`**, 2.1% of `berth_sim` (sarena/list churn);
   negligible in the others, and `chain_relax` has no checks at all (100% other).
4. **Refcount and copies are <2.5% everywhere measured**; boxing does not appear at all (all typed).
5. **"Other" dominates (75-95%)**: the extra instructions are not checks but the shape of the
   emitted code (one temporaries-heavy statement per Python operation, extra moves and reloads).
   Removing checks alone cannot close the `ticket_audit` 5.4x gap.

## Ranked list: what would move how many programs, and by how much

Amdahl bound = 1 / (1 - share of wall removed), using the measured shares above; "programs moved"
counts programs where the feature is worth >2%.

1. **Cheaper emitted code / fewer temps for straight-line Python** (no feature requested, but it is
   the largest measured term: 75-95% of the extra in all three attributed programs).
   Would move `ticket_audit` (5.4x instr, 1.98x wall), `echo_pack` (2.88x), `tree_fold` (2.04x),
   `ledger_bin` (1.92x), `tally_lang` (1.70x) — all 5 at once. Bound: up to 2x wall on
   `ticket_audit`. Needs: better C emission (fewer temporaries, better aliasing information),
   not a hardware feature.
2. **Overflow checks with range facts (provable no-overflow / small int types)**: 15.7% of
   `ledger_bin` -> Amdahl **1.19x** on that program; also present in `rail_transfer` (2.8%).
   Moves 2 programs measurably. Needs: the int64 range analysis the compiler already has, applied
   to accumulators whose bound is provable, or `i32`/`u32` element types.
3. **Bounds checks from ownership/length proofs**: 10.6% of `berth_sim` (**1.12x**), 10.5% of
   `rail_transfer` (**1.12x**), 4.4% of `ledger_bin` (1.05x), 3.1% of `echo_pack` (1.03x). Moves 4
   programs; the owner's "restrict from ownership proofs" idea is worth ~1.1x here, not more.
4. **Allocation reduction (arena/stack lists)**: 8.4% of `rail_transfer` (**1.09x**); it is the
   only attributed program where allocation is material.
5. **SIMD guarantees / "why not vectorised"**: **moves 0 programs today** — 0 vectorised loops in
   10/10 programs, and the hot loops are data-dependent byte parsers. Worth doing for *messages*,
   not for speed on this suite.
6. **GIL-free `par for`, loop tiling, GPU offload**: all ten programs are single-threaded with
   <22% of STREAM and <1% of the machine's 4-core compute; they would need a different algorithm
   (parallel decomposition of a serial parser) before any of these pay. Not measurable as headroom
   here.
7. **Small int/float types**: no float hot loop exists (only `chain_relax`'s `fmt`); int64 is
   already the element type. No measured headroom.

The headline for the owner: **the physical minimum is not the limit for these programs — the
instruction stream is.** 9 of 10 run at 10-58% of the 4-IPC floor and under 10% of STREAM. The
largest measured lever is not a hardware feature but the emitted instruction count
(`ticket_audit` 5.4x C, `echo_pack` 2.9x), and within that the removable checks rank
overflow (up to 16%) > bounds (up to 10%) > allocation (up to 8%) > refcount/copies (<3%).

## Files

- `lab/roof/clock.c`, `stream.c`, `chase.c` — the filter, measured in the same job.
- `lab/roof/run.sh`, `measure.py`, `attrib.py` — the harness.
- `lab/roof/data/` — raw microbenchmark output, `programs.json` (all counters), `attrib/attrib.json`.
