# energy: joules per run of each compare program, and how far each is from the Landauer floor

Measurement only; nothing in the compiler changed. Runner: GitHub Actions, AMD EPYC 7763 (Zen 3),
same 4-vCPU type as roof1. Raw probe in `lab/energy/data/probe.txt`; all rows in
`lab/energy/data/energy.json`; the avoidable-energy split in `lab/energy/data/analysis.json`.
Reproduce with `bash lab/energy/run.sh` (about 30 minutes; the harness installs valgrind under
`$TMPDIR` because the image does not ship it).

## J measured is `n/a`: the runner has no readable package-energy counter

`lab/energy/run.sh probe` found no package-energy source:

- `perf stat -e power/energy-pkg/ true` fails: the vCPUs expose no PMU (`perf_event_paranoid` is 4),
  so there is no `power` PMU and no hardware event at all;
- `/sys/class/powercap` has no `energy_uj` file;
- `/dev/cpu/*/msr` exists but is mode `0600 root:root`; an unprivileged read is denied, so the AMD
  RAPL MSRs (`0xc0010299`, `0xc001029b`) are not available either.

Therefore **every `J measured` cell is `n/a`**. It is stated once here and never invented. No
energy model was fitted to a measured column, because there is no measured column to fit.

## J model: a published-energy estimate, not a package measurement

`J model = instructions x E_instr + LLC misses x 64 B x E_dram`, with one source:

- **E_instr = 0.1 pJ** per retired instruction, the 32-bit integer-add energy from Horowitz,
  *Computing's Energy Problem (and what we can do about it)*, ISSCC 2014, 45 nm;
- **E_dram = 160 pJ/byte**, from the same table: a 32-bit DRAM read costs 640 pJ, i.e. 20 pJ/bit,
  and an LLC miss fetches a 64-byte line (10.24 nJ per miss).

Two honest caveats. (1) The instruction term is only the execute-stage ALU energy: it excludes
instruction fetch, decode, rename, retire, register-file access, L1/L2/L3 dynamic energy, clock
trees and leakage, so it is a **lower-bound dynamic estimate**, not a package-power prediction. For
`tally_lang`, for example, 11.9e9 C instructions cost 1.2 mJ in the model while the program runs for
1.16 s. (2) The DRAM constant is a 45 nm off-chip read, not a 7 nm EPYC DDR4 measurement. The model
is useful for comparing the same program across languages and for ranking avoidable work, which is
what the table uses it for; it is not a wattmeter.

## Instructions and LLC misses

AIL (`typed.py` and `main.py`) and C reuse roof1's `lab/roof/data/programs.json`: the same runner,
the same build commands, and valgrind 3.22 cachegrind with this machine's cache geometry (L1d 32 KiB,
L2 512 KiB, LLC 32 MiB), because the vCPUs expose no hardware PMU. Rust and CPython were measured in
this job with the same cachegrind command and geometry. Per row the method is kept in the JSON.

Coverage of the counters, and why a cell is empty:

- **CPython**: cachegrind finished for `rail_transfer` (3.26e9 instructions), `chain_relax`
  (1.20e11) and `scar_life` (78.5e9). The first pass used a 300 s cap; a second pass with 600 s
  finished `chain_relax`. The remaining seven exceeded it (their native runs are 8-33 s; cachegrind
  is 30-100x slower). Those cells stay `n/a`.
- **AIL building `main.py`**: roof1 already timed out on `chain_relax`, `ledger_bin`, `ticket_audit`
  and `scar_life` (native 49-154 s); `term_rank` has instructions but its cache simulation timed out,
  so its two-term model is `n/a †` and only the instruction term (1.1e-2 J) is known.
- **AIL building `typed.py` and C**: roof1 has all rows except `scar_life`, whose cachegrind run did
  not finish (method `timeout-ir`).
- **Rust**: cachegrind finished for all but `scar_life` (native 38 s).
- `tally_lang/main.py` and `tree_fold/main.py` are **refused by the compiler by name** (a compiled
  pattern used as a value; the same refusal in the base tree), not measurements.

`floor J` = `(instructions + 8 x output bytes) x kT ln 2` at 300 K, `kT ln 2 = 2.871e-21 J`; see the
Landauer section. `x C` and `x Rust` are ratios of `J model`.

| task | lang | source | instructions | LLC miss | J model (est.) | J measured | x C | x Rust | floor J | J/floor |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | ail | typed.py | 8.464e+09 | 7.843e+07 | 8.040e-01 | n/a | 3.60 | 4.08 | 2.43e-11 | 3.31e+10 |
| berth_sim | ail-py | main.py | 3.348e+10 | 2.506e+08 | 2.570e+00 | n/a | 11.52 | 13.04 | 9.61e-11 | 2.67e+10 |
| berth_sim | c | main.c | 5.912e+09 | 2.172e+07 | 2.230e-01 | n/a | 1.00 | 1.13 | 1.70e-11 | 1.31e+10 |
| berth_sim | rust | main.rs | 4.778e+09 | 1.919e+07 | 1.970e-01 | n/a | 0.88 | 1.00 | 1.37e-11 | 1.44e+10 |
| berth_sim | python | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| chain_relax | ail | typed.py | 1.693e+09 | 3.910e+04 | 5.696e-04 | n/a | 0.95 | 1.09 | 4.86e-12 | 1.17e+08 |
| chain_relax | ail-py | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| chain_relax | c | main.c | 1.990e+09 | 3.919e+04 | 6.002e-04 | n/a | 1.00 | 1.15 | 5.71e-12 | 1.05e+08 |
| chain_relax | rust | main.rs | 1.152e+09 | 3.990e+04 | 5.238e-04 | n/a | 0.87 | 1.00 | 3.31e-12 | 1.58e+08 |
| chain_relax | python | main.py | 1.196e+11 | 2.519e+05 | 1.454e-02 | n/a | 24.22 | 27.75 | 3.43e-10 | 4.23e+07 |
| echo_pack | ail | typed.py | 5.543e+09 | 1.118e+07 | 1.151e-01 | n/a | 3.32 | 1.02 | 1.63e-11 | 7.06e+09 |
| echo_pack | ail-py | main.py | 1.823e+10 | 3.638e+07 | 3.743e-01 | n/a | 10.81 | 3.31 | 5.27e-11 | 7.10e+09 |
| echo_pack | c | main.c | 1.924e+09 | 3.362e+06 | 3.462e-02 | n/a | 1.00 | 0.31 | 5.92e-12 | 5.85e+09 |
| echo_pack | rust | main.rs | 1.060e+10 | 1.095e+07 | 1.132e-01 | n/a | 3.27 | 1.00 | 3.08e-11 | 3.67e+09 |
| echo_pack | python | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| ledger_bin | ail | typed.py | 5.235e+09 | 1.445e+07 | 1.484e-01 | n/a | 2.48 | 1.27 | 1.50e-11 | 9.88e+09 |
| ledger_bin | ail-py | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| ledger_bin | c | main.c | 2.733e+09 | 5.824e+06 | 5.991e-02 | n/a | 1.00 | 0.51 | 7.85e-12 | 7.64e+09 |
| ledger_bin | rust | main.rs | 8.550e+09 | 1.131e+07 | 1.166e-01 | n/a | 1.95 | 1.00 | 2.45e-11 | 4.75e+09 |
| ledger_bin | python | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| rail_transfer | ail | typed.py | 3.907e+08 | 4.888e+05 | 5.044e-03 | n/a | 1.14 | 0.97 | 1.12e-12 | 4.50e+09 |
| rail_transfer | ail-py | main.py | 3.704e+09 | 2.333e+07 | 2.392e-01 | n/a | 53.97 | 46.00 | 1.06e-11 | 2.25e+10 |
| rail_transfer | c | main.c | 3.082e+08 | 4.299e+05 | 4.433e-03 | n/a | 1.00 | 0.85 | 8.85e-13 | 5.01e+09 |
| rail_transfer | rust | main.rs | 2.380e+08 | 5.055e+05 | 5.200e-03 | n/a | 1.17 | 1.00 | 6.83e-13 | 7.61e+09 |
| rail_transfer | python | main.py | 3.260e+09 | 1.080e+07 | 1.109e-01 | n/a | 25.02 | 21.32 | 9.36e-12 | 1.18e+10 |
| scar_life | ail | typed.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| scar_life | ail-py | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| scar_life | c | main.c | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| scar_life | rust | main.rs | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| scar_life | python | main.py | 7.850e+10 | 2.855e+06 | 3.709e-02 | n/a | n/a | n/a | 2.25e-10 | 1.64e+08 |
| tally_lang | ail | typed.py | 2.028e+10 | 1.842e+03 | 2.047e-03 | n/a | 1.70 | 1.32 | 5.82e-11 | 3.52e+07 |
| tally_lang | ail-py (refused) | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| tally_lang | c | main.c | 1.190e+10 | 1.648e+03 | 1.207e-03 | n/a | 1.00 | 0.78 | 3.42e-11 | 3.53e+07 |
| tally_lang | rust | main.rs | 1.527e+10 | 2.587e+03 | 1.554e-03 | n/a | 1.29 | 1.00 | 4.38e-11 | 3.54e+07 |
| tally_lang | python | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| term_rank | ail | typed.py | 1.559e+10 | 3.981e+06 | 4.233e-02 | n/a | 1.27 | 0.18 | 4.49e-11 | 9.43e+08 |
| term_rank | ail-py | main.py | 1.115e+11 | n/a | n/a † | n/a | n/a | n/a | 3.20e-10 | 3.48e+07 |
| term_rank | c | main.c | 1.887e+10 | 3.082e+06 | 3.345e-02 | n/a | 1.00 | 0.14 | 5.43e-11 | 6.16e+08 |
| term_rank | rust | main.rs | 1.894e+10 | 2.252e+07 | 2.325e-01 | n/a | 6.95 | 1.00 | 5.45e-11 | 4.27e+09 |
| term_rank | python | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| ticket_audit | ail | typed.py | 1.300e+10 | 1.069e+07 | 1.108e-01 | n/a | 1.48 | 0.47 | 3.73e-11 | 2.97e+09 |
| ticket_audit | ail-py | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| ticket_audit | c | main.c | 2.406e+09 | 7.287e+06 | 7.486e-02 | n/a | 1.00 | 0.32 | 6.91e-12 | 1.08e+10 |
| ticket_audit | rust | main.rs | 1.366e+10 | 2.278e+07 | 2.347e-01 | n/a | 3.13 | 1.00 | 3.92e-11 | 5.98e+09 |
| ticket_audit | python | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| tree_fold | ail | typed.py | 9.053e+09 | 1.061e+08 | 1.088e+00 | n/a | 5.31 | 1.31 | 2.65e-11 | 4.10e+10 |
| tree_fold | ail-py (refused) | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| tree_fold | c | main.c | 4.446e+09 | 1.996e+07 | 2.048e-01 | n/a | 1.00 | 0.25 | 1.33e-11 | 1.54e+10 |
| tree_fold | rust | main.rs | 5.579e+09 | 8.090e+07 | 8.290e-01 | n/a | 4.05 | 1.00 | 1.65e-11 | 5.01e+10 |
| tree_fold | python | main.py | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

`n/a †` means instructions exist but the LLC simulation did not finish, so only the instruction
term is known; the row is not used in a ratio. A `(refused)` row is the compiler's named refusal,
not a measurement.

## What the table says

- **The typed AIL source is close to C in this model**: 0.95x-5.31x, median **1.70x** over the nine
  tasks that have both counters. `chain_relax` is slightly below C (0.95x); the outlier is
  `tree_fold` (5.31x), where AIL's LLC misses are 106.1M against C's 20.0M.
- **The task's plain source is in another class where it was measured**: `berth_sim` 11.52x C,
  `echo_pack` 10.81x, `rail_transfer` 53.97x (median of the three complete rows **11.52x**). This is
  the same split roof1 found on wall time: six of eight compiled `main.py` builds take the boxed
  general path. The four rows with counters are the ones where cachegrind finished.
- **Rust is not automatically the energy floor**: 0.87x-6.95x C, median **1.95x**. It is below C on
  `chain_relax` (0.87x) and `berth_sim` (0.88x), and above on the rest, mostly because its LLC
  misses are higher (`tree_fold` 80.9M vs C 20.0M, `term_rank` 22.5M vs 3.1M).
- **CPython measured 25.0x C on `rail_transfer`** (3.26e9 instructions and 10.8M LLC misses against
  C's 0.31e9 and 0.43M) and **24.2x C on `chain_relax`** (1.20e11 instructions against C's 1.99e9,
  with almost no memory traffic in either). On `scar_life` CPython has counters (78.5e9 instructions)
  but C/AIL/Rust do not, so no ratio is available.
- **In the model, memory traffic is the dominant term where it exists**: `tree_fold` AIL is
  1.088 J, of which 1.087 J is LLC misses; `berth_sim` AIL 0.804 J, of which 0.803 J is LLC misses.
  In `tally_lang` there is almost no memory traffic (1.8K LLC misses) and the instruction term is
  99% of the model.

## Landauer floor: the gap is device physics, not a language

Counting rule: **every retired instruction is counted as one irreversible bit erasure** (a
destination register bit or flag must be overwritten), plus every output bit the program writes;
that is the smallest defensible count, so the floor is a true lower bound. The floor is
`(instructions + 8 x output bytes) x kT ln 2`, with `kT ln 2 = 2.871e-21 J` at 300 K. Across the
rows the floor is 6.8e-13 J to 3.4e-10 J, and `J model / floor` is **3.5e7 to 5.0e10** (the low end
is `tally_lang` and the `term_rank` dagger row, where only the instruction term exists). Even the
most efficient complete rows (`tally_lang`, about 3.5e7x above the floor) are tens of millions of
times above Landauer; the CPython `rail_transfer` row (3.26e9 instructions, floor 9.36e-12 J) is
1.2e10x.

That gap is not something a language can close. The floor assumes one bit erased per instruction and
no other cost; a real CMOS gate spends ~1e5-1e6 kT per switching event, and an off-chip DRAM read
spends ~1e9 kT per 64-byte line. Reaching the floor would need reversible computation, error-free
sub-kT switching and no charge refresh - device physics, not a compiler pass. What a language can do
is remove work: fewer instructions, fewer cache lines, fewer allocations. The model shows how much
of AIL's work is removable, and it is still 7-10 orders of magnitude above Landauer after that.

## Avoidable energy: AIL model energy minus C's

Method: `analyze.py` subtracts C's two-term model from the AIL `typed.py` model for every task that
has both counters, then divides the instruction part by roof1's measured per-category Ir shares
(`lab/roof/data/attrib/attrib.json`, extended in `data/attrib_extra.json` for four more tasks). The
DRAM part (`delta LLC misses x 64 B x E_dram`) is kept as its own line: roof1's seven categories are
source-line patterns, not cache traffic. Attribution covers **9 of 10** programs; `scar_life` still
does not finish under callgrind, so its typed pair has no model and no split. `main.py` has counters
on only three complete rows plus `term_rank` (instructions only), and no attribution, so its totals
are reported without a category split.

| task | d instructions | d instr J | d DRAM J | d total J | split of d instr J |
|---|---:|---:|---:|---:|---|
| berth_sim | +2.551e+09 | +2.551e-04 | +5.807e-01 | +5.809e-01 | other 1.94e-04, bounds 3.86e-05, overflow 8.94e-06, alloc/free 7.26e-06, copies 5.43e-06, refcount 4.79e-07 |
| chain_relax | -2.967e+08 | -2.967e-05 | -9.011e-07 | -3.057e-05 | other -2.97e-05, bounds -1.01e-10, alloc/free -1.16e-10, copies -1.99e-11, refcount -1.33e-11 |
| echo_pack | +3.619e+09 | +3.619e-04 | +8.009e-02 | +8.045e-02 | other 3.44e-04, bounds 1.72e-05, overflow 9.41e-07, alloc/free 1.03e-07, copies 1.21e-12, refcount 1.01e-12 |
| ledger_bin | +2.502e+09 | +2.502e-04 | +8.829e-02 | +8.854e-02 | other 1.54e-04, overflow 7.34e-05, bounds 2.05e-05, alloc/free 1.42e-06, copies 4.74e-07, refcount 1.72e-07 |
| rail_transfer | +8.250e+07 | +8.250e-06 | +6.031e-04 | +6.114e-04 | other 4.44e-06, bounds 1.59e-06, alloc/free 1.27e-06, overflow 4.26e-07, copies 3.36e-07, refcount 1.89e-07 |
| tally_lang | +8.384e+09 | +8.384e-04 | +1.987e-06 | +8.404e-04 | other 8.10e-04, overflow 2.88e-05, bounds 2.07e-09, alloc/free 7.69e-10, copies 8.43e-11, refcount 4.69e-11 |
| term_rank | -3.284e+09 | -3.284e-04 | +9.206e-03 | +8.877e-03 | other -2.02e-04, bounds -4.88e-05, alloc/free -4.89e-05, copies -1.14e-05, overflow -8.63e-06, refcount -8.38e-06 |
| ticket_audit | +1.060e+10 | +1.060e-03 | +3.485e-02 | +3.591e-02 | other 8.56e-04, bounds 5.88e-05, alloc/free 4.51e-05, refcount 4.12e-05, overflow 3.07e-05, copies 2.82e-05 |
| tree_fold | +4.607e+09 | +4.607e-04 | +8.825e-01 | +8.829e-01 | other 2.74e-04, bounds 1.27e-04, overflow 2.57e-05, alloc/free 2.14e-05, copies 1.26e-05, refcount 4.74e-07 |

Signed sum of the instruction categories over these nine programs (the total instruction term is
2.876e-3 J, so the shares sum to 100%):

| rank | category | J | share of d instr J |
|---:|---|---:|---:|
| 1 | other (emitted-code shape) | 2.404e-03 | 83.6% |
| 2 | bounds checks | 2.146e-04 | 7.5% |
| 3 | overflow/range checks | 1.602e-04 | 5.6% |
| 4 | copies | 3.562e-05 | 1.2% |
| 5 | refcount | 3.415e-05 | 1.2% |
| 6 | allocation/free | 2.766e-05 | 1.0% |
| 7 | boxing | 0 | 0% |

`chain_relax` and `term_rank` are negative because their typed AIL build executes fewer model
joules than C in those categories; they reduce the signed sum. `boxing` is zero because every
attributed build is `typed.py`; the boxed general path is exactly where the uncounted `main.py`
instructions live.

`main.py` minus C, totals only (no attribution): `berth_sim` +2.347 J (instruction +2.756e-3,
DRAM +2.344), `echo_pack` +3.397e-1 J (+1.631e-3, +3.381e-1), `rail_transfer` +2.348e-1 J
(+3.396e-4, +2.345e-1). `term_rank` has +9.264e-3 J of instruction energy but no LLC count, so no
two-term total. Three measured `main.py` programs therefore account for 2.92 J of avoidable model
energy, 1.7x the 1.68 J of the nine typed pairs combined.

### Which removal saves the most joules across the ten programs

1. **Memory traffic (LLC misses) - 1.676 J of the 1.679 J typed total (99.8%)**, plus 2.916 J on the
   three measured `main.py` programs. `tree_fold` alone is 0.882 J (86.3M extra LLC misses) and
   `berth_sim` 0.581 J (56.7M). This is the largest lever in the model, and it is not one of roof1's
   seven line categories: it is cache/DRAM behaviour.
2. **`other` emitted-code shape - 2.40e-3 J** on the typed path (83.6% of the instruction term).
3. **Bounds checks - 2.15e-4 J**, led by `tree_fold` (1.27e-4), `ticket_audit` (5.88e-5) and
   `berth_sim` (3.86e-5).
4. **Overflow/range checks - 1.60e-4 J**, led by `ledger_bin` (7.34e-5), `ticket_audit` (3.07e-5)
   and `tally_lang` (2.88e-5).
5. **Copies (3.56e-5 J), refcount (3.42e-5 J), allocation/free (2.77e-5 J)** are the next three and
   are an order of magnitude smaller each; **boxing is not measurable on the typed path** and has no
   attribution on `main.py`, though `term_rank`'s 1.1e11 instructions are the place to look for it.

So the answer to "what should AIL remove first" is not a check: in the model, cutting cache misses
(arena/stack lists, fewer temporaries and copies that touch memory, contiguous layouts) is worth
about 600x the whole instruction-category difference, and the general path's boxed work is worth
another 1.7x on just three programs. A check-elision pass is worth millijoules here; memory behaviour
is worth joules.


## Files

- `lab/energy/run.sh` - RAPL probe, valgrind bootstrap into `$TMPDIR`, then `measure.py`.
- `lab/energy/measure.py` - builds C/Rust, reuses roof1's AIL/C counters, measures Rust/CPython with
  cachegrind, reads the perf input from each task's `gen.py`, and writes `data/energy.json`.
- `lab/energy/analyze.py` - the table above and the avoidable-energy split
  (`data/analysis.json`), using roof1's `data/attrib/attrib.json`.
- `lab/energy/data/` - `probe.txt`, `energy.json`, `analysis.json`, `attrib_extra.json` (attribution
  for the four programs roof1 did not attribute).
