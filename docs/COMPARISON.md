# AIL language comparison

AIL commit `4f1245b`; date 2026-11-02; 10 tasks; run 41393616319; fixture `tools/testdata/compare-report.json`.

## Toolchain versions

| tool | version |
|---|---|
| gcc | gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 |
| rustc | rustc 1.99.1 (58cf8f9c3 2026-10-13) |
| go | go version go1.24.13 linux/amd64 |
| nim | Nim Compiler Version 2.2.12 [Linux: amd64] |
| python | 3.12.3 |
| valgrind | valgrind-3.22.0 |

Pins: GCC=13.3.0; RUSTC=1.99.1; GO=1.24.13; NIM=2.2.12; PYTHON=3.12.

| toolchain | KiB |
|---|---:|
| C | 420,000 |
| Rust | 780,000 |
| Go | 610,000 |
| Nim | 350,000 |
| Python | 180,000 |
| AIL | 90,000 |

## Scorecards

### AIL vs Rust

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| berth_sim | general | 10/10 | L 1.56x | L 1.27x | W 0.02x | L 17.10x | L 2.00x | L 1.68x |
| chain_relax | general | 10/10 | L 1.47x | W 0.95x | W 0.01x | L 9.84x | W 0.80x | L 1.21x |
| echo_pack | typed | 10/10 | W 0.61x | L 1.00x | W 0.02x | L 9.64x | L 1.88x | W 0.49x |
| ledger_bin | general | 10/10 | W 0.33x | L 1.23x | W 0.02x | L 9.79x | L 1.88x | W 0.30x |
| rail_transfer | general | 10/10 | L 15.00x | W 0.95x | W 0.01x | L 9.40x | L 1.75x | L 17.96x |
| scar_life | general | 10/10 | W 0.82x | W 0.95x | W 0.01x | L 8.78x | L 1.71x | W 0.57x |
| tally_lang | general | 10/10 | L 1.07x | W 0.95x | W 0.01x | L 9.81x | W 0.86x | W 0.94x |
| term_rank | typed | 10/10 | W 0.87x | W 0.95x | W 0.02x | L 9.48x | L 1.71x | W 0.77x |
| ticket_audit | typed | 10/10 | W 0.62x | W 0.95x | W 0.02x | L 9.47x | L 1.79x | W 0.44x |
| tree_fold | general | 10/10 | L 1.06x | L 1.48x | W 0.02x | L 19.95x | L 2.00x | L 1.05x |
| **W / n** | | | **5/10** | **6/10** | **10/10** | **0/10** | **2/10** | **6/10** |

### AIL vs the best other language

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| berth_sim | general | 10/10 | L 1.56x | L 1.27x | W 0.02x | L 17.10x | L 2.00x | L 1.68x |
| chain_relax | general | 10/10 | L 1.47x | W 0.95x | W 0.01x | L 9.84x | W 0.80x | L 1.37x |
| echo_pack | typed | 10/10 | W 0.61x | L 1.00x | W 0.02x | L 9.64x | L 1.88x | L 1.88x |
| ledger_bin | general | 10/10 | W 0.33x | L 1.23x | W 0.02x | L 9.79x | L 1.88x | L 1.72x |
| rail_transfer | general | 10/10 | L 15.00x | W 0.95x | W 0.01x | L 9.40x | L 1.75x | L 17.96x |
| scar_life | general | 10/10 | W 0.82x | W 0.95x | W 0.01x | L 8.78x | L 1.71x | L 1.03x |
| tally_lang | general | 10/10 | L 1.07x | W 0.95x | W 0.01x | L 9.81x | W 0.86x | L 1.81x |
| term_rank | typed | 10/10 | W 0.87x | W 0.95x | W 0.02x | L 9.48x | L 1.71x | W 0.94x |
| ticket_audit | typed | 10/10 | W 0.62x | W 0.95x | W 0.02x | L 9.47x | L 1.79x | L 2.02x |
| tree_fold | general | 10/10 | L 1.06x | L 1.48x | W 0.02x | L 19.95x | L 2.00x | L 2.08x |
| **W / n** | | | **5/10** | **6/10** | **10/10** | **0/10** | **2/10** | **1/10** |

### AIL (py src) vs Rust

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| berth_sim | general | 10/10 | L 1.56x | L 1.27x | W 0.02x | L 17.10x | L 2.00x | L 1.68x |
| chain_relax | refused | n/a | - | - | - | - | - | - |
| echo_pack | general | 10/10 | W 0.61x | L 1.00x | W 0.02x | L 9.64x | L 1.88x | W 0.49x |
| ledger_bin | general | 10/10 | W 0.33x | L 1.23x | W 0.02x | L 9.79x | L 1.88x | W 0.30x |
| rail_transfer | refused | n/a | - | - | - | - | - | - |
| scar_life | general | 10/10 | W 0.82x | W 0.95x | W 0.01x | L 8.78x | L 1.71x | W 0.57x |
| tally_lang | general | 10/10 | L 1.07x | W 0.95x | W 0.01x | L 9.81x | W 0.86x | W 0.94x |
| term_rank | general | 10/10 | W 0.87x | W 0.95x | W 0.02x | L 9.48x | L 1.71x | W 0.77x |
| ticket_audit | general | 10/10 | W 0.62x | W 0.95x | W 0.02x | L 9.47x | L 1.79x | W 0.44x |
| tree_fold | general | 10/10 | L 1.06x | L 1.48x | W 0.02x | L 19.95x | L 2.00x | L 1.05x |
| **W / n** | | | **5/8** | **4/8** | **8/8** | **0/8** | **1/8** | **6/8** |

### AIL (py src) vs the best other language

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| berth_sim | general | 10/10 | L 1.56x | L 1.27x | W 0.02x | L 17.10x | L 2.00x | L 1.68x |
| chain_relax | refused | n/a | - | - | - | - | - | - |
| echo_pack | general | 10/10 | W 0.61x | L 1.00x | W 0.02x | L 9.64x | L 1.88x | L 1.88x |
| ledger_bin | general | 10/10 | W 0.33x | L 1.23x | W 0.02x | L 9.79x | L 1.88x | L 1.72x |
| rail_transfer | refused | n/a | - | - | - | - | - | - |
| scar_life | general | 10/10 | W 0.82x | W 0.95x | W 0.01x | L 8.78x | L 1.71x | L 1.03x |
| tally_lang | general | 10/10 | L 1.07x | W 0.95x | W 0.01x | L 9.81x | W 0.86x | L 1.81x |
| term_rank | general | 10/10 | W 0.87x | W 0.95x | W 0.02x | L 9.48x | L 1.71x | W 0.94x |
| ticket_audit | general | 10/10 | W 0.62x | W 0.95x | W 0.02x | L 9.47x | L 1.79x | L 2.02x |
| tree_fold | general | 10/10 | L 1.06x | L 1.48x | W 0.02x | L 19.95x | L 2.00x | L 2.08x |
| **W / n** | | | **5/8** | **4/8** | **8/8** | **0/8** | **1/8** | **1/8** |

## Metrics

### Instructions (user space)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | 6.40G | 6.40G | n/a | 4.10G | not run | not run | not run | 4.10G (Rust) | 1.56x | 1.56x | 1.56x | 1.56x |
| chain_relax | 2.20G | build failed | n/a | 1.50G | not run | not run | not run | 1.50G (Rust) | 1.47x | 1.47x | - | - |
| echo_pack | 1.10G | 1.10G | n/a | 1.80G | not run | not run | not run | 1.80G (Rust) | 0.61x | 0.61x | 0.61x | 0.61x |
| ledger_bin | 900.00M | 900.00M | n/a | 2.70G | not run | not run | not run | 2.70G (Rust) | 0.33x | 0.33x | 0.33x | 0.33x |
| rail_transfer | 1.50G | build failed | build failed | 100.00M | not run | not run | not run | 100.00M (Rust) | 15.00x | 15.00x | - | - |
| scar_life | 18.00G | 18.00G | n/a | 22.00G | not run | not run | not run | 22.00G (Rust) | 0.82x | 0.82x | 0.82x | 0.82x |
| tally_lang | 3.10G | 3.10G | n/a | 2.90G | not run | not run | not run | 2.90G (Rust) | 1.07x | 1.07x | 1.07x | 1.07x |
| term_rank | 4.00G | 4.00G | n/a | 4.60G | not run | not run | not run | 4.60G (Rust) | 0.87x | 0.87x | 0.87x | 0.87x |
| ticket_audit | 3.40G | 3.40G | n/a | 5.50G | not run | not run | not run | 5.50G (Rust) | 0.62x | 0.62x | 0.62x | 0.62x |
| tree_fold | 5.20G | 5.20G | n/a | 4.90G | not run | not run | not run | 4.90G (Rust) | 1.06x | 1.06x | 1.06x | 1.06x |
| **geomean** |  |  |  |  |  |  |  |  | **1.13x** (n=10) | **1.13x** (n=10) | **0.79x** (n=8) | **0.79x** (n=8) |

### Peak RSS (MiB, /usr/bin/time -v)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | 239.2 | 239.2 | n/a | 187.7 | not run | not run | not run | 187.7 (Rust) | 1.27x | 1.27x | 1.27x | 1.27x |
| chain_relax | 3.9 | build failed | n/a | 4.1 | not run | not run | not run | 4.1 (Rust) | 0.95x | 0.95x | - | - |
| echo_pack | 346.1 | 346.1 | n/a | 344.6 | not run | not run | not run | 344.6 (Rust) | 1.00x | 1.00x | 1.00x | 1.00x |
| ledger_bin | 337.0 | 337.0 | n/a | 273.8 | not run | not run | not run | 273.8 (Rust) | 1.23x | 1.23x | 1.23x | 1.23x |
| rail_transfer | 25.4 | build failed | build failed | 26.7 | not run | not run | not run | 26.7 (Rust) | 0.95x | 0.95x | - | - |
| scar_life | 17.4 | 17.4 | n/a | 18.2 | not run | not run | not run | 18.2 (Rust) | 0.95x | 0.95x | 0.95x | 0.95x |
| tally_lang | 1.9 | 1.9 | n/a | 2.0 | not run | not run | not run | 2.0 (Rust) | 0.95x | 0.95x | 0.95x | 0.95x |
| term_rank | 157.9 | 157.9 | n/a | 165.8 | not run | not run | not run | 165.8 (Rust) | 0.95x | 0.95x | 0.95x | 0.95x |
| ticket_audit | 248.8 | 248.8 | n/a | 261.3 | not run | not run | not run | 261.3 (Rust) | 0.95x | 0.95x | 0.95x | 0.95x |
| tree_fold | 464.6 | 464.6 | n/a | 314.9 | not run | not run | not run | 314.9 (Rust) | 1.48x | 1.48x | 1.48x | 1.48x |
| **geomean** |  |  |  |  |  |  |  |  | **1.06x** (n=10) | **1.06x** (n=10) | **1.08x** (n=8) | **1.08x** (n=8) |

### Binary size (KiB, as built)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | 102 | 102 | n/a | 4518 | not run | not run | not run | 4518 (Rust) | 0.02x | 0.02x | 0.02x | 0.02x |
| chain_relax | 34 | build failed | n/a | 4450 | not run | not run | not run | 4450 (Rust) | 0.01x | 0.01x | - | - |
| echo_pack | 71 | 71 | n/a | 4485 | not run | not run | not run | 4485 (Rust) | 0.02x | 0.02x | 0.02x | 0.02x |
| ledger_bin | 88 | 88 | n/a | 4502 | not run | not run | not run | 4502 (Rust) | 0.02x | 0.02x | 0.02x | 0.02x |
| rail_transfer | 45 | build failed | build failed | 4461 | not run | not run | not run | 4461 (Rust) | 0.01x | 0.01x | - | - |
| scar_life | 63 | 63 | n/a | 4479 | not run | not run | not run | 4479 (Rust) | 0.01x | 0.01x | 0.01x | 0.01x |
| tally_lang | 57 | 57 | n/a | 4473 | not run | not run | not run | 4473 (Rust) | 0.01x | 0.01x | 0.01x | 0.01x |
| term_rank | 92 | 92 | n/a | 4506 | not run | not run | not run | 4506 (Rust) | 0.02x | 0.02x | 0.02x | 0.02x |
| ticket_audit | 79 | 79 | n/a | 4493 | not run | not run | not run | 4493 (Rust) | 0.02x | 0.02x | 0.02x | 0.02x |
| tree_fold | 96 | 96 | n/a | 4510 | not run | not run | not run | 4510 (Rust) | 0.02x | 0.02x | 0.02x | 0.02x |
| **geomean** |  |  |  |  |  |  |  |  | **0.02x** (n=10) | **0.02x** (n=10) | **0.02x** (n=8) | **0.02x** (n=8) |

### Compile time (s, median of 3 cold builds)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | 7.01 | 7.01 | n/a | 0.41 | not run | not run | not run | 0.41 (Rust) | 17.10x | 17.10x | 17.10x | 17.10x |
| chain_relax | 1.87 | build failed | n/a | 0.19 | not run | not run | not run | 0.19 (Rust) | 9.84x | 9.84x | - | - |
| echo_pack | 2.41 | 2.41 | n/a | 0.25 | not run | not run | not run | 0.25 (Rust) | 9.64x | 9.64x | 9.64x | 9.64x |
| ledger_bin | 2.74 | 2.74 | n/a | 0.28 | not run | not run | not run | 0.28 (Rust) | 9.79x | 9.79x | 9.79x | 9.79x |
| rail_transfer | 1.88 | build failed | build failed | 0.20 | not run | not run | not run | 0.20 (Rust) | 9.40x | 9.40x | - | - |
| scar_life | 2.02 | 2.02 | n/a | 0.23 | not run | not run | not run | 0.23 (Rust) | 8.78x | 8.78x | 8.78x | 8.78x |
| tally_lang | 3.04 | 3.04 | n/a | 0.31 | not run | not run | not run | 0.31 (Rust) | 9.81x | 9.81x | 9.81x | 9.81x |
| term_rank | 2.56 | 2.56 | n/a | 0.27 | not run | not run | not run | 0.27 (Rust) | 9.48x | 9.48x | 9.48x | 9.48x |
| ticket_audit | 4.45 | 4.45 | n/a | 0.47 | not run | not run | not run | 0.47 (Rust) | 9.47x | 9.47x | 9.47x | 9.47x |
| tree_fold | 11.17 | 11.17 | n/a | 0.56 | not run | not run | not run | 0.56 (Rust) | 19.95x | 19.95x | 19.95x | 19.95x |
| **geomean** |  |  |  |  |  |  |  |  | **10.87x** (n=10) | **10.87x** (n=10) | **11.21x** (n=8) | **11.21x** (n=8) |

### Build disk (MiB, fresh build dir with its caches)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | 175.78 | 175.78 | n/a | 87.89 | not run | not run | not run | 87.89 (Rust) | 2.00x | 2.00x | 2.00x | 2.00x |
| chain_relax | 58.59 | build failed | n/a | 73.24 | not run | not run | not run | 73.24 (Rust) | 0.80x | 0.80x | - | - |
| echo_pack | 146.48 | 146.48 | n/a | 78.12 | not run | not run | not run | 78.12 (Rust) | 1.88x | 1.88x | 1.88x | 1.88x |
| ledger_bin | 156.25 | 156.25 | n/a | 83.01 | not run | not run | not run | 83.01 (Rust) | 1.88x | 1.88x | 1.88x | 1.88x |
| rail_transfer | 68.36 | build failed | build failed | 39.06 | not run | not run | not run | 39.06 (Rust) | 1.75x | 1.75x | - | - |
| scar_life | 117.19 | 117.19 | n/a | 68.36 | not run | not run | not run | 68.36 (Rust) | 1.71x | 1.71x | 1.71x | 1.71x |
| tally_lang | 92.77 | 92.77 | n/a | 107.42 | not run | not run | not run | 107.42 (Rust) | 0.86x | 0.86x | 0.86x | 0.86x |
| term_rank | 136.72 | 136.72 | n/a | 80.08 | not run | not run | not run | 80.08 (Rust) | 1.71x | 1.71x | 1.71x | 1.71x |
| ticket_audit | 166.02 | 166.02 | n/a | 92.77 | not run | not run | not run | 92.77 (Rust) | 1.79x | 1.79x | 1.79x | 1.79x |
| tree_fold | 195.31 | 195.31 | n/a | 97.66 | not run | not run | not run | 97.66 (Rust) | 2.00x | 2.00x | 2.00x | 2.00x |
| **geomean** |  |  |  |  |  |  |  |  | **1.57x** (n=10) | **1.57x** (n=10) | **1.68x** (n=8) | **1.68x** (n=8) |

### Wall time (ms, median of 5 timed runs of the perf input)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | 2472 | 2472 | 1635 | 1470 | not run | not run | not run | 1470 (Rust) | 1.68x | 1.68x | 1.68x | 1.68x |
| chain_relax | 1256 | build failed | 920 | 1037 | not run | not run | not run | 920 (C) | 1.21x | 1.37x | - | - |
| echo_pack | 934 | 934 | 496 | 1895 | not run | not run | not run | 496 (C) | 0.49x | 1.88x | 0.49x | 1.88x |
| ledger_bin | 840 | 840 | 487 | 2833 | not run | not run | not run | 487 (C) | 0.30x | 1.72x | 0.30x | 1.72x |
| rail_transfer | 862 | build failed | build failed | 48 | not run | not run | not run | 48 (Rust) | 17.96x | 17.96x | - | - |
| scar_life | 16696 | 16696 | 16264 | 29534 | not run | not run | not run | 16264 (C) | 0.57x | 1.03x | 0.57x | 1.03x |
| tally_lang | 1548 | 1548 | 854 | 1640 | not run | not run | not run | 854 (C) | 0.94x | 1.81x | 0.94x | 1.81x |
| term_rank | 2260 | 2260 | 2393 | 2925 | not run | not run | not run | 2393 (C) | 0.77x | 0.94x | 0.77x | 0.94x |
| ticket_audit | 1887 | 1887 | 933 | 4248 | not run | not run | not run | 933 (C) | 0.44x | 2.02x | 0.44x | 2.02x |
| tree_fold | 1866 | 1866 | 898 | 1783 | not run | not run | not run | 898 (C) | 1.05x | 2.08x | 1.05x | 2.08x |
| **geomean** |  |  |  |  |  |  |  |  | **1.00x** (n=10) | **1.99x** (n=10) | **0.68x** (n=8) | **1.59x** (n=8) |

## AIL path and refusals

| task | AIL path | AIL (py src) path | AIL cases | AIL (py src) cases | AIL note | AIL (py src) note |
|---|---|---|---|---|---|---|
| berth_sim | general | general | 10/10 | 10/10 | why not typed: a call can raise or have side effects | why not typed: a call can raise or have side effects |
| chain_relax | general | refused | 10/10 | n/a | why not typed: a call can raise or have side effects | refused: a call can raise or have side effects |
| echo_pack | typed | general | 10/10 | 10/10 | - | why not typed: a call can raise or have side effects |
| ledger_bin | general | general | 10/10 | 10/10 | why not typed: a call can raise or have side effects | why not typed: a call can raise or have side effects |
| rail_transfer | general | refused | 10/10 | n/a | why not typed: a call can raise or have side effects | refused: a call can raise or have side effects |
| scar_life | general | general | 10/10 | 10/10 | why not typed: a call can raise or have side effects | why not typed: a call can raise or have side effects |
| tally_lang | general | general | 10/10 | 10/10 | why not typed: a call can raise or have side effects | why not typed: a call can raise or have side effects |
| term_rank | typed | general | 10/10 | 10/10 | - | why not typed: a call can raise or have side effects |
| ticket_audit | typed | general | 10/10 | 10/10 | - | why not typed: a call can raise or have side effects |
| tree_fold | general | general | 10/10 | 10/10 | why not typed: a call can raise or have side effects | why not typed: a call can raise or have side effects |

## Method

- Build: gcc -O2 -std=c11; rustc -C opt-level=3; go build; nim c -d:release; AIL `compile` (default build); CPython runs the source.
- Compile time: wall time of the build command, median of 3 cold builds, each in a fresh directory with its own AIL_CACHE, TMPDIR, GOCACHE, GOPATH, nimcache and XDG cache.
- Build disk: `du -sk` of that fresh directory after the first build (binary, caches, leftovers), minus the empty scaffold.
- AIL path: `compile --strict` accepting the program means typed; otherwise the default build used the general path (the reason is quoted).
- Instructions: `perf_event_open` (tools/icount.c) when the runner exposes the counter, otherwise valgrind callgrind Ir. User space only.
- Correctness: every public and hidden case of the task (gen.py) is run in every language; stdout and exit code must equal the CPython reference.py output.
- Wall time: median of 5 runs of the perf input (2-3 when one run takes more than 15 s). Same runner for every language.
- Peak RSS: `/usr/bin/time -v` Maximum resident set size, median of the timed runs.
