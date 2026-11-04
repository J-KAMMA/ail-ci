# tsv_join: measured results

- Date: 2026-11-04 (UTC)
- Commit: `3357c8b` (this branch, based on the `integ` export `1f15d31`; the result JSON records `head`)
- Runner: GitHub Actions, Linux 7.0.0-1017-azure, 4 CPUs, image `20261101.360.1` (shared host, so
  wall times carry noise; instruction counts do not)
- Toolchains: gcc 13.3.0, rustc 1.75.0 (apt; the pinned 1.99.1 is not installed on this runner and
  `rustup` had no toolchain — see below), go 1.24.13, CPython 3.12.3, valgrind 3.22.0. `nim` is not
  installed and there is no `main.nim`; the Nim column is `not run`.
- Task: `tasks/tsv_join` (spec, generator, reference oracle), perf input 300,000 users and 4,000,000
  orders / 99.9 MB.
- Result: every written program matches the CPython reference on all 9 public and hidden cases and on
  the perf input, exit status 0.

## Column paths

- `ail` (`typed.py`): **typed path** (`compile --strict` accepts it).
- `ail-py` (`main.py`): **general path**; the default build prints
  `note: built on the general path (about 20x slower) because fields returns a tuple on one path and a
  single value on another; run with --strict to see why`.
- `c`, `rust`, `go`, `python`: no AIL path.

`typed.py` and `main.py` run the same one-pass algorithm (a hash map from `user_id` to `(name,
country)`, a second pass accumulating per user and per country, then two sorts). The spelling differs
only where the typed path needs it:

- `typed.py` is annotated (`dict[int, int]`, `dict[str, int]`, `list[int]`, `list[str]`, `bytes`,
  `-> int`), uses `ail`'s `read_stdin_bytes`/`write_stdout_bytes`, index lists (`uid`, `uname`,
  `uctry`, `uamt`, `unum`, `cname`, `camt`, `cnum`) instead of dicts of tuples, decodes a country
  once to a `str` for the country map key, and uses `-1` as the invalid-number sentinel.
- `main.py` is unannotated, uses `sys.stdin.buffer.read`/`sys.stdout.write`, returns `None` from the
  field splitter on a malformed line, and keys the user map by the parsed `int`. That `None` is why
  its AIL build falls back to the general path.

Neither program changes the algorithm to reach a path; only the spelling does.

## Table

The table below is the output of `python3 lab/compare/merge.py /tmp/cand-results` on the one result
JSON, with the callgrind instruction counts injected (see the notes). `n/a` in an instructions cell
means the count was not measured, not that the program is wrong: both columns matched on the perf
input. `nim` was not run (no toolchain, no source), so its cells read `not run`.


AIL commit `3357c8b`; 1 tasks; instruction counts by `callgrind`; smoke run: no.
Every program was run on the same input and its stdout and exit code compared with the CPython `reference.py` of the task. Ratios are AIL / best other language for that row (below 1.00: AIL is better, all metrics are lower-is-better). Best-other covers C, Rust, Go, Nim and Python, and only programs whose output matched.

### Status: output vs the CPython reference, and AIL path

| task | input | AIL | AIL (py src) | C | Rust | Go | Nim | Python | AIL path | AIL(py) path |
|---|---|---|---|---|---|---|---|---|---|---|
| tsv_join | 99.9 MB | match | match | match | match | match | not run | match | typed | general (fields returns a tuple on one path and a single value on another) |

### Correctness: public + hidden cases matching the CPython reference (passed/total)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python |
|---|---|---|---|---|---|---|---|
| tsv_join | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | not run | 9/9 |

### Scorecard: AIL vs the best other language per column (W = lower than every other, L = not)

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| tsv_join | typed | 9/9 | L 2.07x | L 2.94x | L 4.25x | L 27.62x | L 12.83x | L 1.64x |
| **wins** | | | **0/1** | **0/1** | **0/1** | **0/1** | **0/1** | **0/1** |

Where AIL loses: tsv_join instr 2.07x; tsv_join RSS 2.94x; tsv_join binary 4.25x; tsv_join compile 27.62x; tsv_join disk 12.83x; tsv_join wall 1.64x

### Scorecard: AIL (py src) vs the best other language per column (W = lower than every other, L = not)

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| tsv_join | general | 9/9 | - | L 7.93x | L 20.28x | L 91.75x | L 55.17x | L 153.79x |
| **wins** | | | **0/0** | **0/1** | **0/1** | **0/1** | **0/1** | **0/1** |

Where AIL (py src) loses: tsv_join RSS 7.93x; tsv_join binary 20.28x; tsv_join compile 91.75x; tsv_join disk 55.17x; tsv_join wall 153.79x

### Instructions (user space)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| tsv_join | 6.42G | n/a | 3.10G | 5.82G | 15.11G | not run | n/a | 3.10G (C) | 2.07x | - |
| **geomean** |  |  |  |  |  |  |  |  | **2.07x** (n=1) | - |

### Peak RSS (MiB, /usr/bin/time -v)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| tsv_join | 380.4 | 1026.4 | 129.5 | 149.7 | 289.6 | not run | 236.6 | 129.5 (C) | 2.94x | 7.93x |
| **geomean** |  |  |  |  |  |  |  |  | **2.94x** (n=1) | **7.93x** (n=1) |

### Binary size (KiB, as built)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| tsv_join | 89 | 424 | 21 | 13003 | 2241 | not run | - | 21 (C) | 4.25x | 20.28x |
| **geomean** |  |  |  |  |  |  |  |  | **4.25x** (n=1) | **20.28x** (n=1) |

### Compile time (s, median of 3 cold builds)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| tsv_join | 4.39 | 14.59 | 0.16 | 1.01 | 5.66 | not run | - | 0.16 (C) | 27.62x | 91.75x |
| **geomean** |  |  |  |  |  |  |  |  | **27.62x** (n=1) | **91.75x** (n=1) |

### Build disk (MiB, fresh build dir with its caches)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| tsv_join | 0.30 | 1.29 | 0.02 | 12.70 | 37.45 | not run | - | 0.02 (C) | 12.83x | 55.17x |
| **geomean** |  |  |  |  |  |  |  |  | **12.83x** (n=1) | **55.17x** (n=1) |

### Wall time (ms, median of 5 timed runs of the perf input)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| tsv_join | 1146 | 107656 | 700 | 1929 | 2161 | not run | 32497 | 700 (C) | 1.64x | 153.79x |
| **geomean** |  |  |  |  |  |  |  |  | **1.64x** (n=1) | **153.79x** (n=1) |

### Toolchain install size (KiB, `du -sk`, once)

| language | KiB |
|---|---:|
| C | 124,048 |
| Rust | 185,436 |
| Go | 293,412 |
| Python | 62,820 |
| AIL | 41,732 |

### Method

- Build: gcc -O2 -std=c11; rustc -C opt-level=3; go build; nim c -d:release; AIL `compile` (default build); CPython runs the source.
- Compile time: wall time of the build command, median of 3 cold builds, each in a fresh directory with its own AIL_CACHE, TMPDIR, GOCACHE, GOPATH, nimcache and XDG cache.
- Build disk: `du -sk` of that fresh directory after the first build (binary, caches, leftovers), minus the empty scaffold.
- AIL path: `compile --strict` accepting the program means typed; otherwise the default build used the general path (the reason is quoted).
- Instructions: `perf_event_open` (tools/icount.c) when the runner exposes the counter, otherwise valgrind callgrind Ir. User space only.
- Correctness: every public and hidden case of the task (gen.py) is run in every language; stdout and exit code must equal the CPython reference.py output.
- Wall time: median of 5 runs of the perf input (2-3 when one run takes more than 15 s). Same runner for every language.
- Peak RSS: `/usr/bin/time -v` Maximum resident set size, median of the timed runs.

## Notes on the measurement

- Memory: a first full run under `ulimit -v 1500000` matched on every column except Go and measured
  the same peak RSS (highest `ail-py` at 1026.4 MiB, under the cap). The final combined run used
  `ulimit -v 4000000` so that Go's runtime, which reserves a large *virtual* address space at startup,
  does not abort (it exits 2 under a 1.5 GB virtual cap although its peak RSS is 289.6 MiB). The
  result JSON is that final run; every peak RSS is below 1.1 GB.
- Instructions: this runner exposes no hardware counter (`perf_event_open: Permission denied`), so
  counts come from `valgrind --tool=callgrind` Ir on the perf input. C, Rust, Go and `ail` were counted
  (3.10G, 5.82G, 15.11G and 6.42G). `python` and `ail-py` were **not** counted: a callgrind pass at
  this input size is far beyond the budget. Those two cells are `n/a`; their wall, RSS, binary and case
  results are measured. Go needs `GODEBUG=asyncpreemptoff=1` under valgrind, as in `csv_rollup`.
- Rust: the runner had `rustc` only through a `rustup` shim with no toolchain installed, so rustc
  1.75.0 was installed with apt. The program uses std only and builds unchanged; the pinned 1.99.1 was
  not available. The toolchain size row is `/usr/lib/rustlib` + `/usr/bin/rustdoc`, because the apt
  rustc reports `/usr` as its sysroot and `du -sk /usr` is not a meaningful toolchain size.
- Go build: `go build -o out src/main.go` on a single file works without a module; no `go.mod` is
  needed and none was added.

## Integer probe (not part of the cases)

The spec bounds every sum to 4 * 10^14, well inside int64. A hand probe outside those ranges drives
an addition past int64 the way an unbounded per-country sum would (`/tmp/probes/join_sum_overflow.py`,
`a = int(argv[1]); b = int(argv[2]); print(a + b)` with `5000000000000000000` twice):

| probe | CPython 3.12 | AIL default build | AIL `AIL_UNIFIED_FORCE=1` |
|---|---|---|---|
| `join_sum_overflow.py 5000000000000000000 5000000000000000000` | prints `10000000000000000000`, exit 0 | `OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)`, exit 1, no stdout | same `OverflowError`, exit 1, no stdout |

AIL stops loudly in both builds and never prints a wrong number. The probe was compiled with
`ail_chatgpt.py compile --syntax python` and run on this commit. The task's own validation rejects
every out-of-range field before any addition, so the task programs never reach the overflow.

## Reproduce

    ulimit -v 1500000
    PATH=/usr/bin:$PATH python3 lab/compare_cand/run.py --task tsv_join --out /tmp/r.json \
        --langs ail,ail-py,c,rust,go,python
    # Go needs a looser virtual cap (its runtime reserves address space):
    ulimit -v 4000000
    PATH=/usr/bin:$PATH python3 lab/compare_cand/run.py --task tsv_join --out /tmp/r_go.json --langs go
    # copy r_go's go record over r's, then build the table:
    mkdir -p /tmp/cand-results && cp /tmp/r.json /tmp/cand-results/result-tsv_join.json
    python3 lab/compare/merge.py /tmp/cand-results --json /tmp/cand.json

Instruction counts need a second callgrind pass (`run.py --icount callgrind`), which is why they were
counted separately here.
