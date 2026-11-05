# log_scan: measured results

- Date: 2026-11-05 (UTC)
- Commit: `3c3c0a3` (this branch; the result JSON records the same `head`)
- Runner: GitHub Actions, Linux 7.0.0-1014-aws, 4 CPUs, image `20261018.96.1` (shared host, so
  wall times carry noise; instruction counts would not)
- Toolchains: gcc 13.3.0, rustc 1.99.1, go 1.24.13, CPython 3.12.3. `nim` is not installed and there
  is no `main.nim`, so the Nim column is `not run`. `valgrind` is not installed and
  `perf_event_open` is denied on this runner, so the instruction counts were **not measured**; those
  cells are `n/a` (see the notes).
- Task: `tasks/log_scan` (spec, generator, reference oracle), perf input 1,500,000 lines /
  125,748,300 bytes (about 125.7 MB).
- Result: every written program matches the CPython reference on all 3 public and 6 hidden cases and
  on the perf input, exit status 0.

## Column paths

- `ail` (`typed.py`): **typed path** (`compile --strict` accepts it; the default build produces the
  same binary).
- `ail-py` (`main.py`): **general path**; the default build prints
  `note: lab/compare_cand/src/log_scan/main.py:11:9: built on the general path (about 20x slower)
  because the constant None; this language has no null value, so nothing holds one -- build a linked
  structure as parallel index lists (left[] and right[] of int, -1 where Python would put None) and
  walk it with a list used as an explicit stack; run with --strict to see why`.
  The strict probe's own reason is `comparing a str with a number; str and bytes are separate types
  here and a str is never a number`.
- `c`, `rust`, `go`, `python`: no AIL path.

`typed.py` and `main.py` run the same one-pass algorithm (scan each line, a hash map from path to
`(count, bytes)`, a hash set of IP values, 24 hour buckets, then a sort of the paths). The spelling
differs only where the typed path needs it:

- `typed.py` is annotated (`dict[str, int]`, `list[int]`, `list[str]`, `set[int]`, `bytes`, `-> int`),
  uses `ail`'s `read_stdin_bytes`/`write_stdout_bytes`, an index scanner over the raw bytes, packed
  month constants, and separate index lists for the paths. It keeps the six parsed fields in a
  small `P` class because a `list` parameter is read-only on the typed path. Invalid numbers use
  `-1` as the sentinel.
- `main.py` is unannotated, uses `sys.stdin.read()`, `str.split(' ')` (exactly ten tokens proves the
  single spaces), `str.partition` for the date and clock fields, a `dict` and a `set`, and manual
  digit loops with a cap so an oversized `BYTES` field is bad instead of an overflow.

Neither program changes the algorithm to reach a path; only the spelling does.

## Table

The table below is the output of `python3 lab/compare/merge.py /tmp/cand-results` on the one result
JSON. `nim` was not run (no toolchain, no source), so its cells read `not run`. The instructions
row is all `n/a` because neither counter was available (see the notes); every other metric was
measured on this runner.


AIL commit `3c3c0a3`; 1 tasks; instruction counts by `none`; smoke run: no.
Every program was run on the same input and its stdout and exit code compared with the CPython `reference.py` of the task. Ratios are AIL / best other language for that row (below 1.00: AIL is better, all metrics are lower-is-better). Best-other covers C, Rust, Go, Nim and Python, and only programs whose output matched.

### Status: output vs the CPython reference, and AIL path

| task | input | AIL | AIL (py src) | C | Rust | Go | Nim | Python | AIL path | AIL(py) path |
|---|---|---|---|---|---|---|---|---|---|---|
| log_scan | 125.7 MB | match | match | match | match | match | not run | match | typed | general (comparing a str with a number; str and bytes are separate types here and a str is never a ) |

### Correctness: public + hidden cases matching the CPython reference (passed/total)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python |
|---|---|---|---|---|---|---|---|
| log_scan | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | not run | 9/9 |

### Scorecard: AIL vs the best other language per column (W = lower than every other, L = not)

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| log_scan | typed | 9/9 | - | L 1.58x | L 2.95x | L 20.90x | L 9.33x | L 2.83x |
| **wins** | | | **0/0** | **0/1** | **0/1** | **0/1** | **0/1** | **0/1** |

Where AIL loses: log_scan RSS 1.58x; log_scan binary 2.95x; log_scan compile 20.90x; log_scan disk 9.33x; log_scan wall 2.83x

### Scorecard: AIL (py src) vs the best other language per column (W = lower than every other, L = not)

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| log_scan | general | 9/9 | - | L 4.91x | L 11.68x | L 39.15x | L 35.00x | L 43.63x |
| **wins** | | | **0/0** | **0/1** | **0/1** | **0/1** | **0/1** | **0/1** |

Where AIL (py src) loses: log_scan RSS 4.91x; log_scan binary 11.68x; log_scan compile 39.15x; log_scan disk 35.00x; log_scan wall 43.63x

### Instructions (user space)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| log_scan | n/a | n/a | n/a | n/a | n/a | not run | n/a | - | - | - |
| **geomean** |  |  |  |  |  |  |  |  | - | - |

### Peak RSS (MiB, /usr/bin/time -v)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| log_scan | 193.2 | 601.3 | 123.7 | 122.6 | 378.1 | not run | 328.7 | 122.6 (Rust) | 1.58x | 4.91x |
| **geomean** |  |  |  |  |  |  |  |  | **1.58x** (n=1) | **4.91x** (n=1) |

### Binary size (KiB, as built)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| log_scan | 60 | 238 | 20 | 4495 | 2238 | not run | - | 20 (C) | 2.95x | 11.68x |
| **geomean** |  |  |  |  |  |  |  |  | **2.95x** (n=1) | **11.68x** (n=1) |

### Compile time (s, median of 3 cold builds)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| log_scan | 3.68 | 6.89 | 0.18 | 0.40 | 4.65 | not run | - | 0.18 (C) | 20.90x | 39.15x |
| **geomean** |  |  |  |  |  |  |  |  | **20.90x** (n=1) | **39.15x** (n=1) |

### Build disk (MiB, fresh build dir with its caches)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| log_scan | 0.22 | 0.82 | 0.02 | 4.39 | 37.44 | not run | - | 0.02 (C) | 9.33x | 35.00x |
| **geomean** |  |  |  |  |  |  |  |  | **9.33x** (n=1) | **35.00x** (n=1) |

### Wall time (ms, median of 5 timed runs of the perf input)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| log_scan | 696 | 10720 | 246 | 370 | 699 | not run | 7243 | 246 (C) | 2.83x | 43.63x |
| **geomean** |  |  |  |  |  |  |  |  | **2.83x** (n=1) | **43.63x** (n=1) |

### Toolchain install size (KiB, `du -sk`, once)

| language | KiB |
|---|---:|
| C | 124,048 |
| Rust | 631,320 |
| Go | 293,408 |
| Python | 62,820 |
| AIL | 42,508 |

### Tools

- gcc: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
- rustc: rustc 1.99.1 (58cf8f9c3 2026-10-13)
- go: go version go1.24.13 linux/amd64
- nim: missing (FileNotFoundError)
- python: 3.12.3
- valgrind: missing (FileNotFoundError)

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

- **Instructions are not measured.** This runner exposes no hardware counter
  (`perf_event_open: Permission denied`), and `valgrind` is not installed. Installing it with `apt`
  was blocked by the runner's command policy, so the callgrind path could not be used either. Every
  instruction cell is `n/a`; all other metrics were measured. A previous run that asked for
  callgrind recorded `FileNotFoundError` for all four columns, which is the same cause.
- **Memory.** The full run used `ulimit -v 4000000` so that Go's runtime, which reserves a large
  *virtual* address space at startup, does not abort. Peak RSS stayed well below the 1.5 GB rule:
  the highest is `ail-py` at 601.3 MiB, then Go at 378.1 MiB and Python at 328.7 MiB.
- **Nim** was skipped: there is no `nim` binary and no `main.nim`, so the column is `not run` rather
  than a failed build.
- **Wall time** is noisy on this shared host (for example the `ail` median moved between 448 ms and
  696 ms across two identical runs); the other metrics were stable.

## Integer probe (not part of the cases)

The spec keeps every sum inside int64, and a line whose `BYTES` is outside 0 .. 10^12 is bad, so the
task programs never reach an overflow. A hand input with ten lines of
`BYTES = 2000000000000000000` (outside the spec) is classified as bad by both the CPython reference
and the AIL typed build; both print `lines 1 bad 10`, `bytes 5` and exit 0. A separate probe drives
the summation itself past int64 (`/tmp/probes/log_sum_overflow.py`, `total = total + int(tok)` over
ten argv values of `2000000000000000000`):

| probe | CPython 3.12 | AIL default build | AIL `AIL_UNIFIED_FORCE=1` |
|---|---|---|---|
| `log_sum_overflow.py 2000000000000000000` x10 | prints `20000000000000000000`, exit 0 | `OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)`, exit 1, no stdout | same `OverflowError`, exit 1, no stdout |

AIL stops loudly in both builds and never prints a wrong number.

## Reproduce

    ulimit -v 4000000
    PATH=/usr/bin:$PATH python3 lab/compare_cand/run.py --task log_scan --out /tmp/r.json \
        --langs ail,ail-py,c,rust,go,python --icount none
    mkdir -p /tmp/cand-results && cp /tmp/r.json /tmp/cand-results/result-log_scan.json
    python3 lab/compare/merge.py /tmp/cand-results --json /tmp/cand.json

`--icount none` is used because neither instruction counter is available here. Omitting it makes the
run try callgrind and record `FileNotFoundError`; the case and perf results are unchanged.
