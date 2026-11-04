# csv_rollup: measured results

- Date: 2026-11-04 (UTC)
- Commit: `af3a23d` (`cmpcand1`, on `integ` + this branch; the result JSON records `head`)
- Runner: GitHub Actions, Linux 7.0.0-1017-azure, 4 CPUs, image `20261101.360.1` (shared: up to five
  agents on the host, so the wall times carry noticeable noise; the instruction counts do not)
- Toolchains: gcc 13.3.0, rustc 1.99.1, go 1.24.13, CPython 3.12.3, valgrind 3.22.0. `nim` is not
  installed on this runner and there is no `main.nim`; the Nim column is `not run`.
- Task: `tasks/csv_rollup` (spec, generator, reference oracle), perf input 4,000,000 rows / 89.1 MB.
- Result: every program matches the CPython reference on all 9 public and hidden cases and on the perf
  input, exit status 0.

## Column paths

- `ail` (`typed.py`): **typed path** (`compile --strict` accepts it).
- `ail-py` (`main.py`): **general path**; the default build prints
  `note: .../main.py:29:9: built on the general path (about 20x slower) because the constant None; this
  language has no null value, so nothing holds one ... run with --strict to see why`.
- `c`, `rust`, `go`, `python`: no AIL path.

## Table

The table below is the output of `python3 lab/compare/merge.py /tmp/cand-results` on the one result
JSON from `lab/compare_cand/run.py`, with the callgrind instruction counts injected (see
the notes). `n/a` in an instructions cell means the count was not measured, not that the program is
wrong: both columns still matched on the perf input.


AIL commit `af3a23d`; 1 tasks; instruction counts by `callgrind`; smoke run: no.
Every program was run on the same input and its stdout and exit code compared with the CPython `reference.py` of the task. Ratios are AIL / best other language for that row (below 1.00: AIL is better, all metrics are lower-is-better). Best-other covers C, Rust, Go, Nim and Python, and only programs whose output matched.

### Status: output vs the CPython reference, and AIL path

| task | input | AIL | AIL (py src) | C | Rust | Go | Nim | Python | AIL path | AIL(py) path |
|---|---|---|---|---|---|---|---|---|---|---|
| csv_rollup | 89.1 MB | match | match | match | match | match | not run | match | typed | general (the constant None; this language has no null value, so nothing holds one) |

### Correctness: public + hidden cases matching the CPython reference (passed/total)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python |
|---|---|---|---|---|---|---|---|
| csv_rollup | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | not run | 9/9 |

### Scorecard: AIL vs the best other language per column (W = lower than every other, L = not)

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| csv_rollup | typed | 9/9 | L 2.76x | L 6.29x | L 3.07x | L 20.14x | L 9.50x | L 2.83x |
| **wins** | | | **0/1** | **0/1** | **0/1** | **0/1** | **0/1** | **0/1** |

Where AIL loses: csv_rollup instr 2.76x; csv_rollup RSS 6.29x; csv_rollup binary 3.07x; csv_rollup compile 20.14x; csv_rollup disk 9.50x; csv_rollup wall 2.83x

### Scorecard: AIL (py src) vs the best other language per column (W = lower than every other, L = not)

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| csv_rollup | general | 9/9 | - | L 5.94x | L 19.52x | L 82.85x | L 52.17x | L 86.42x |
| **wins** | | | **0/0** | **0/1** | **0/1** | **0/1** | **0/1** | **0/1** |

Where AIL (py src) loses: csv_rollup RSS 5.94x; csv_rollup binary 19.52x; csv_rollup compile 82.85x; csv_rollup disk 52.17x; csv_rollup wall 86.42x

### Instructions (user space)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| csv_rollup | 11.23G | n/a | 4.07G | 8.71G | 6.69G | not run | n/a | 4.07G (C) | 2.76x | - |
| **geomean** |  |  |  |  |  |  |  |  | **2.76x** (n=1) | - |

### Peak RSS (MiB, /usr/bin/time -v)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| csv_rollup | 662.7 | 625.4 | 105.4 | 118.4 | 271.9 | not run | 157.1 | 105.4 (C) | 6.29x | 5.94x |
| **geomean** |  |  |  |  |  |  |  |  | **6.29x** (n=1) | **5.94x** (n=1) |

### Binary size (KiB, as built)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| csv_rollup | 64 | 404 | 21 | 4504 | 2257 | not run | - | 21 (C) | 3.07x | 19.52x |
| **geomean** |  |  |  |  |  |  |  |  | **3.07x** (n=1) | **19.52x** (n=1) |

### Compile time (s, median of 3 cold builds)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| csv_rollup | 2.68 | 11.02 | 0.13 | 0.48 | 4.99 | not run | - | 0.13 (C) | 20.14x | 82.85x |
| **geomean** |  |  |  |  |  |  |  |  | **20.14x** (n=1) | **82.85x** (n=1) |

### Build disk (MiB, fresh build dir with its caches)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| csv_rollup | 0.22 | 1.22 | 0.02 | 4.40 | 37.43 | not run | - | 0.02 (C) | 9.50x | 52.17x |
| **geomean** |  |  |  |  |  |  |  |  | **9.50x** (n=1) | **52.17x** (n=1) |

### Wall time (ms, median of 5 timed runs of the perf input)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| csv_rollup | 2524 | 76994 | 891 | 2245 | 1498 | not run | 27339 | 891 (C) | 2.83x | 86.42x |
| **geomean** |  |  |  |  |  |  |  |  | **2.83x** (n=1) | **86.42x** (n=1) |

### Toolchain install size (KiB, `du -sk`, once)

| language | KiB |
|---|---:|
| C | 124,048 |
| Rust | 1,563,104 |
| Go | 293,412 |
| Python | 62,820 |
| AIL | 41,692 |

### Tools

- gcc: gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
- rustc: rustc 1.99.1 (58cf8f9c3 2026-10-13)
- go: go version go1.24.13 linux/amd64
- nim: missing (FileNotFoundError)
- python: 3.12.3
- valgrind: valgrind-3.22.0

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

- Instructions: this runner exposes no hardware counter (`perf_event_open` returns
  `ENOENT`/"No supported events found" even with `kernel.perf_event_paranoid=1`), so counts come from
  `valgrind --tool=callgrind` Ir on the perf input. C, Rust, Go and `ail` were counted (4.07G, 8.71G,
  6.69G and 11.23G instructions). `python` and `ail-py` instruction counts were **not** obtained:
  each callgrind run at this input size is far slower than the 80-minute budget allows (the Python
  run was still going after 20 minutes and was stopped). Those two cells are `n/a`; their wall, RSS,
  binary and case results are measured.
- Go under valgrind aborts with the Go runtime's preemption machinery, so its count uses
  `GODEBUG=asyncpreemptoff=1`; same program, same output, 6.69G Ir. Without the variable valgrind
  cannot run it.
- Memory: the runner was given `ulimit -v 4000000` rather than `1500000`. Go's runtime reserves a
  large virtual address space at startup, and a 1.5 GB *virtual* cap makes it panic intermittently
  (exit 2) although its peak RSS is only 272 MiB. Peak RSS, which is what the 1.5 GB rule protects,
  stays under 700 MiB for every column (the highest is `ail` at 663 MiB).
- Wall time is the median of the timed runs in `run_task.py` (5, or 2-3 when one run exceeds 15 s);
  the host was shared, so compare columns on the same row rather than across runs. The numbers shown
  are from one run with no other local work; the `python` and `ail-py` columns are dominated by the
  interpreter and the general path respectively.
- `ail-py` builds the plain Python source and its compiled binary peaks at 625 MiB; the interpreter
  (`python`) peaks at 157 MiB. Earlier drafts that used `bytes.split` pushed the `ail-py` build to
  1.39 GB and OOMed, which is why `main.py` scans the buffer by index (see `README.md`).

## Behaviour probes (outside the cases)

`qty * price` and every sum stay inside int64 for all inputs the spec allows. Beyond int64, AIL
stops loudly in both the default build and with `AIL_UNIFIED_FORCE=1` and never prints a wrong
number; CPython prints the exact big integer. Details and the four probe programs are in
`README.md`. The probes were run, and the results recorded there, on this commit.

## Reproduce

    ulimit -v 4000000
    python3 lab/compare_cand/run.py --task csv_rollup --out /tmp/r.json \
        --langs ail,ail-py,c,rust,go,python
    mkdir -p /tmp/cand-results && cp /tmp/r.json /tmp/cand-results/result-csv_rollup.json
    python3 lab/compare/merge.py /tmp/cand-results --json /tmp/cand.json

The instruction counts require a second, callgrind pass; `run.py --icount callgrind` does both in one
run if the host has the time.
