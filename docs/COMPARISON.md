# AIL language comparison

AIL commit `4f1245b`; date 2026-11-02; 10 tasks; run 41393616319; fixture `tools/testdata/compare-report.json`.

## Toolchain versions

No tool versions in the report.

## Scorecards

### AIL vs Rust

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| berth_sim | - | n/a | - | L 1.27x | - | - | - | L 1.68x |
| chain_relax | - | n/a | - | - | - | - | - | L 1.21x |
| echo_pack | - | n/a | - | L 1.00x | - | - | - | W 0.49x |
| ledger_bin | - | n/a | - | L 1.23x | - | - | - | W 0.30x |
| rail_transfer | - | n/a | - | - | - | - | - | L 17.96x |
| scar_life | - | n/a | - | - | - | - | - | W 0.57x |
| tally_lang | - | n/a | - | - | - | - | - | W 0.94x |
| term_rank | - | n/a | - | - | - | - | - | W 0.77x |
| ticket_audit | - | n/a | - | - | - | - | - | W 0.44x |
| tree_fold | - | n/a | - | L 1.48x | - | - | - | L 1.05x |
| **W / n** | | | **0/0** | **0/4** | **0/0** | **0/0** | **0/0** | **6/10** |

### AIL vs the best other language

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| berth_sim | - | n/a | - | L 1.27x | - | - | - | L 1.68x |
| chain_relax | - | n/a | - | - | - | - | - | L 1.21x |
| echo_pack | - | n/a | - | L 1.00x | - | - | - | W 0.49x |
| ledger_bin | - | n/a | - | L 1.23x | - | - | - | W 0.30x |
| rail_transfer | - | n/a | - | - | - | - | - | L 17.96x |
| scar_life | - | n/a | - | - | - | - | - | W 0.57x |
| tally_lang | - | n/a | - | - | - | - | - | W 0.94x |
| term_rank | - | n/a | - | - | - | - | - | W 0.77x |
| ticket_audit | - | n/a | - | - | - | - | - | W 0.44x |
| tree_fold | - | n/a | - | L 1.48x | - | - | - | L 1.05x |
| **W / n** | | | **0/0** | **0/4** | **0/0** | **0/0** | **0/0** | **6/10** |

### AIL (py src) vs Rust

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| berth_sim | not run | n/a | - | - | - | - | - | - |
| chain_relax | not run | n/a | - | - | - | - | - | - |
| echo_pack | not run | n/a | - | - | - | - | - | - |
| ledger_bin | not run | n/a | - | - | - | - | - | - |
| rail_transfer | not run | n/a | - | - | - | - | - | - |
| scar_life | refused | n/a | - | - | - | - | - | - |
| tally_lang | refused | n/a | - | - | - | - | - | - |
| term_rank | not run | n/a | - | - | - | - | - | - |
| ticket_audit | not run | n/a | - | - | - | - | - | - |
| tree_fold | refused | n/a | - | - | - | - | - | - |
| **W / n** | | | **0/0** | **0/0** | **0/0** | **0/0** | **0/0** | **0/0** |

### AIL (py src) vs the best other language

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| berth_sim | not run | n/a | - | - | - | - | - | - |
| chain_relax | not run | n/a | - | - | - | - | - | - |
| echo_pack | not run | n/a | - | - | - | - | - | - |
| ledger_bin | not run | n/a | - | - | - | - | - | - |
| rail_transfer | not run | n/a | - | - | - | - | - | - |
| scar_life | refused | n/a | - | - | - | - | - | - |
| tally_lang | refused | n/a | - | - | - | - | - | - |
| term_rank | not run | n/a | - | - | - | - | - | - |
| ticket_audit | not run | n/a | - | - | - | - | - | - |
| tree_fold | refused | n/a | - | - | - | - | - | - |
| **W / n** | | | **0/0** | **0/0** | **0/0** | **0/0** | **0/0** | **0/0** |

## Metrics

### Instructions (user space)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| chain_relax | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| echo_pack | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| ledger_bin | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| rail_transfer | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| scar_life | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| tally_lang | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| term_rank | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| ticket_audit | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| tree_fold | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| **geomean** |  |  |  |  |  |  |  |  | - | - | - | - |

### Peak RSS (MiB, /usr/bin/time -v)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | 239.2 | not run | not run | 187.7 | not run | not run | not run | 187.7 (Rust) | 1.27x | 1.27x | - | - |
| chain_relax | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| echo_pack | 346.1 | not run | not run | 344.6 | not run | not run | not run | 344.6 (Rust) | 1.00x | 1.00x | - | - |
| ledger_bin | 337.0 | not run | not run | 273.8 | not run | not run | not run | 273.8 (Rust) | 1.23x | 1.23x | - | - |
| rail_transfer | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| scar_life | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| tally_lang | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| term_rank | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| ticket_audit | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| tree_fold | 464.6 | build failed | not run | 314.9 | not run | not run | not run | 314.9 (Rust) | 1.48x | 1.48x | - | - |
| **geomean** |  |  |  |  |  |  |  |  | **1.23x** (n=4) | **1.23x** (n=4) | - | - |

### Binary size (KiB, as built)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| chain_relax | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| echo_pack | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| ledger_bin | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| rail_transfer | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| scar_life | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| tally_lang | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| term_rank | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| ticket_audit | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| tree_fold | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| **geomean** |  |  |  |  |  |  |  |  | - | - | - | - |

Supplied range (no per-task values): AIL 34–102; Rust 4450–4518; AIL lower on 10/10 tasks.

### Compile time (s, median of 3 cold builds)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| chain_relax | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| echo_pack | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| ledger_bin | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| rail_transfer | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| scar_life | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| tally_lang | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| term_rank | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| ticket_audit | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| tree_fold | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| **geomean** |  |  |  |  |  |  |  |  | - | - | - | - |

Supplied range (no per-task values): AIL 1.87–11.17; Rust 0.19–0.56; AIL lower on 0/10 tasks.

### Build disk (MiB, fresh build dir with its caches)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| chain_relax | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| echo_pack | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| ledger_bin | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| rail_transfer | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| scar_life | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| tally_lang | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| term_rank | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| ticket_audit | n/a | not run | not run | n/a | not run | not run | not run | - | - | - | - | - |
| tree_fold | n/a | build failed | not run | n/a | not run | not run | not run | - | - | - | - | - |
| **geomean** |  |  |  |  |  |  |  |  | - | - | - | - |

### Wall time (ms, median of 5 timed runs of the perf input)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL/Rust | AIL/best | AIL(py)/Rust | AIL(py)/best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| berth_sim | 2472 | not run | not run | 1470 | not run | not run | not run | 1470 (Rust) | 1.68x | 1.68x | - | - |
| chain_relax | 1256 | not run | not run | 1037 | not run | not run | not run | 1037 (Rust) | 1.21x | 1.21x | - | - |
| echo_pack | 934 | not run | not run | 1895 | not run | not run | not run | 1895 (Rust) | 0.49x | 0.49x | - | - |
| ledger_bin | 840 | not run | not run | 2833 | not run | not run | not run | 2833 (Rust) | 0.30x | 0.30x | - | - |
| rail_transfer | 862 | not run | not run | 48 | not run | not run | not run | 48 (Rust) | 17.96x | 17.96x | - | - |
| scar_life | 16696 | build failed | not run | 29534 | not run | not run | not run | 29534 (Rust) | 0.57x | 0.57x | - | - |
| tally_lang | 1548 | build failed | not run | 1640 | not run | not run | not run | 1640 (Rust) | 0.94x | 0.94x | - | - |
| term_rank | 2260 | not run | not run | 2925 | not run | not run | not run | 2925 (Rust) | 0.77x | 0.77x | - | - |
| ticket_audit | 1887 | not run | not run | 4248 | not run | not run | not run | 4248 (Rust) | 0.44x | 0.44x | - | - |
| tree_fold | 1866 | build failed | not run | 1783 | not run | not run | not run | 1783 (Rust) | 1.05x | 1.05x | - | - |
| **geomean** |  |  |  |  |  |  |  |  | **1.00x** (n=10) | **1.00x** (n=10) | - | - |

## AIL path and refusals

| task | AIL path | AIL (py src) path | AIL cases | AIL (py src) cases | AIL note | AIL (py src) note |
|---|---|---|---|---|---|---|
| berth_sim | - | not run | n/a | n/a | - | - |
| chain_relax | - | not run | n/a | n/a | - | - |
| echo_pack | - | not run | n/a | n/a | - | - |
| ledger_bin | - | not run | n/a | n/a | - | - |
| rail_transfer | - | not run | n/a | n/a | - | - |
| scar_life | - | refused | n/a | n/a | - | refused: import of 're' with a use that is not built |
| tally_lang | - | refused | n/a | n/a | - | refused: locals()/vars()/eval/exec in a function with a possibly-unassigned local |
| term_rank | - | not run | n/a | n/a | - | - |
| ticket_audit | - | not run | n/a | n/a | - | - |
| tree_fold | - | refused | n/a | n/a | - | refused: import of 're' with a use that is not built |

## Method

- Build: gcc -O2 -std=c11; rustc -C opt-level=3; go build; nim c -d:release; AIL `compile` (default build); CPython runs the source.
- Compile time: wall time of the build command, median of 3 cold builds, each in a fresh directory with its own AIL_CACHE, TMPDIR, GOCACHE, GOPATH, nimcache and XDG cache.
- Build disk: `du -sk` of that fresh directory after the first build (binary, caches, leftovers), minus the empty scaffold.
- AIL path: `compile --strict` accepting the program means typed; otherwise the default build used the general path (the reason is quoted).
- Instructions: `perf_event_open` (tools/icount.c) when the runner exposes the counter, otherwise valgrind callgrind Ir. User space only.
- Correctness: every public and hidden case of the task (gen.py) is run in every language; stdout and exit code must equal the CPython reference.py output.
- Wall time: median of 5 runs of the perf input (2-3 when one run takes more than 15 s). Same runner for every language.
- Peak RSS: `/usr/bin/time -v` Maximum resident set size, median of the timed runs.
