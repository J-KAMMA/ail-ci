# grid_bfs: measured results

- Date: 2026-11-05 (UTC)
- Commit: `e970474` (this branch; the result JSON records the same `head`)
- Runner: GitHub Actions, Linux 7.0.0-1017-azure, 4 CPUs, image `20261101.360.1` (shared host, so
  wall times carry noise; the instruction counts would not)
- Toolchains: gcc 13.3.0, rustc 1.99.1, go 1.24.13, CPython 3.12.3. `nim` is not installed and there
  is no `main.nim`, so the Nim column is `not run`. `valgrind` is not installed and
  `perf_event_open` is denied on this runner, so the instruction counts were **not measured**; those
  cells are `n/a` (see the notes).
- Task: `tasks/grid_bfs` (spec, generator, reference oracle). Perf input: a 2000 x 2000 grid at 30%
  walls with 20 queries, 4,002,374 bytes.
- Result: every program matches the CPython reference on all 3 public and 6 hidden cases and on the
  perf input, exit status 0.

## Column paths

- `ail` (`typed.py`): **typed path** (`compile --strict` accepts it; the default build produces the
  same binary, and `fallback_notes` is 0).
- `ail-py` (`main.py`): **general path**; the default build prints
  `note: .../src/grid_bfs/main.py:75:5: built on the general path (about 20x slower) because 'flat'
  is an int and is being assigned a str; a local's kind is settled by its FIRST assignment and never
  changes afterwards -- give the second kind a different name, or use the value inline without
  binding it to one; run with --strict to see why`.
- `c`, `rust`, `go`, `python`: no AIL path.

`typed.py` and `main.py` run the same algorithm; only the spelling differs:

- `typed.py` is annotated (`list[int]`, `list[bytes]`, `dict`-free, `-> int`), reads the grid with
  `ail`'s `read_stdin_bytes`, validates with `bytes.split(b'\n')`, joins the rows into one flat
  `bytes` grid with `b''.join`, and prints with `print(f'...')`. It uses `-1` as the only sentinel
  and keeps the four query columns in four parallel `list[int]`s, because a list parameter is
  read-only on the typed path.
- `main.py` is unannotated, reads text with `sys.stdin.read()`, works on `str` rows and a flat
  `str` grid (`''.join`), and writes one `'\n'.join(...)` block with `sys.stdout.write`.

Both parse the header, every grid row and every query **before** printing anything, so a malformed
input (short/long row, bad byte, out-of-range or malformed query, missing or extra line) reaches the
same `exit 2` with empty stdout. Neither program changes the BFS: one flat distance array reset per
query, one flat array as a FIFO queue, neighbours up, down, left, right, target tested on dequeue.

## Table

The table below is the output of `python3 lab/compare/merge.py /tmp/gb/results2` on the one result
JSON. `nim` was not run (no toolchain, no source), so its cells read `not run`. The instructions row
is all `n/a` because neither counter was available (see the notes); every other metric was measured
on this runner.


AIL commit `e970474`; 1 tasks; instruction counts by `none`; smoke run: no.
Every program was run on the same input and its stdout and exit code compared with the CPython `reference.py` of the task. Ratios are AIL / best other language for that row (below 1.00: AIL is better, all metrics are lower-is-better). Best-other covers C, Rust, Go, Nim and Python, and only programs whose output matched.

### Status: output vs the CPython reference, and AIL path

| task | input | AIL | AIL (py src) | C | Rust | Go | Nim | Python | AIL path | AIL(py) path |
|---|---|---|---|---|---|---|---|---|---|---|
| grid_bfs | 4.0 MB | match | match | match | match | match | not run | match | typed | general ('flat' is an int and is being assigned a str; a local's kind is settled by its FIRST assig) |

### Correctness: public + hidden cases matching the CPython reference (passed/total)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python |
|---|---|---|---|---|---|---|---|
| grid_bfs | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | not run | 9/9 |

### Scorecard: AIL vs the best other language per column (W = lower than every other, L = not)

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| grid_bfs | typed | 9/9 | - | L 2.36x | L 2.38x | L 18.25x | L 7.60x | L 1.48x |
| **wins** | | | **0/0** | **0/1** | **0/1** | **0/1** | **0/1** | **0/1** |

Where AIL loses: grid_bfs RSS 2.36x; grid_bfs binary 2.38x; grid_bfs compile 18.25x; grid_bfs disk 7.60x; grid_bfs wall 1.48x

### Scorecard: AIL (py src) vs the best other language per column (W = lower than every other, L = not)

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| grid_bfs | general | 9/9 | - | L 25.19x | L 10.40x | L 65.29x | L 27.20x | L 33.07x |
| **wins** | | | **0/0** | **0/1** | **0/1** | **0/1** | **0/1** | **0/1** |

Where AIL (py src) loses: grid_bfs RSS 25.19x; grid_bfs binary 10.40x; grid_bfs compile 65.29x; grid_bfs disk 27.20x; grid_bfs wall 33.07x

### Instructions (user space)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| grid_bfs | n/a | n/a | n/a | n/a | n/a | not run | n/a | - | - | - |
| **geomean** |  |  |  |  |  |  |  |  | - | - |

### Peak RSS (MiB, /usr/bin/time -v)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| grid_bfs | 81.6 | 871.7 | 34.6 | 35.1 | 39.3 | not run | 255.1 | 34.6 (C) | 2.36x | 25.19x |
| **geomean** |  |  |  |  |  |  |  |  | **2.36x** (n=1) | **25.19x** (n=1) |

### Binary size (KiB, as built)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| grid_bfs | 38 | 167 | 16 | 4452 | 2202 | not run | - | 16 (C) | 2.38x | 10.40x |
| **geomean** |  |  |  |  |  |  |  |  | **2.38x** (n=1) | **10.40x** (n=1) |

### Compile time (s, median of 3 cold builds)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| grid_bfs | 1.77 | 6.33 | 0.10 | 0.23 | 5.45 | not run | - | 0.10 (C) | 18.25x | 65.29x |
| **geomean** |  |  |  |  |  |  |  |  | **18.25x** (n=1) | **65.29x** (n=1) |

### Build disk (MiB, fresh build dir with its caches)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| grid_bfs | 0.15 | 0.53 | 0.02 | 4.35 | 36.79 | not run | - | 0.02 (C) | 7.60x | 27.20x |
| **geomean** |  |  |  |  |  |  |  |  | **7.60x** (n=1) | **27.20x** (n=1) |

### Wall time (ms, median of 5 timed runs of the perf input)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| grid_bfs | 585 | 13064 | 400 | 395 | 439 | not run | 10080 | 395 (Rust) | 1.48x | 33.07x |
| **geomean** |  |  |  |  |  |  |  |  | **1.48x** (n=1) | **33.07x** (n=1) |

### Toolchain install size (KiB, `du -sk`, once)

| language | KiB |
|---|---:|
| C | 124,048 |
| Rust | 631,324 |
| Go | 293,412 |
| Python | 62,820 |
| AIL | 43,332 |

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

- **Instructions are not measured.** This runner exposes no hardware counter and `valgrind` is not
  installed, so every instruction cell is `n/a`; all other metrics were measured. The method is
  recorded as `none` in the JSON.
- **Memory.** The full run used `ulimit -v 1500000` as the task asks. Go builds and runs under the
  1.5 GB virtual cap on this runner (unlike the earlier `log_scan`/`csv_rollup` runs, where it
  panicked intermittently and a 4 GB cap was used). Peak RSS: `ail-py` 871.7 MiB, Python 255.1 MiB,
  Go 39.3 MiB, Rust 35.1 MiB, C 34.6 MiB, `ail` 81.6 MiB -- all below the 1.5 GB rule.
- **Nim** was skipped: no `nim` binary and no `main.nim`, so the column is `not run`.
- **Wall time** is noisy on this shared host. The `ail` typed column is the closest to the best other
  language here (1.48x, Rust 395 ms vs AIL 585 ms); the pinned work is memory-bandwidth bound
  (each query touches up to 4M distance slots and 4M queue slots).
- Why `ail-py` peaks near 872 MiB: the general path keeps Python objects for the 4M-element `dist`
  list and the 4M-element `queue` list. That is still inside the 1.5 GB cap.

## Probes (outside the cases)

All six programs were run on the same hand inputs with `bash ~/tools/cmp.sh`-style comparisons; the
reference is CPython 3.12 `reference.py`.

### Malformed inputs

Each of `empty`, `short_row`, `long_row`, `bad_byte`, `bad_query_range`, `query_3_tokens`,
`missing_line`, `extra_line`, `huge_token` (a 20-digit header value) and `h_too_big` (`H = 2001`)
makes **all six** programs (`ail`, `ail-py`, `c`, `rust`, `go`, `python`) exit **2 with empty
stdout**, exactly like `reference.py`. A valid 2 x 3 control input gives the same 22-byte output from
all six.

### Integers

Every value the spec allows is small (`H,W <= 2000`, coordinates `< 2000`), and each parser caps its
accumulator at `10^8`, so no program reaches an int64 overflow. A header token of 20 nines
(`99999999999999999999`) is rejected as malformed before any arithmetic:

| probe | CPython 3.12 | AIL default (`typed.py`, typed) | AIL `AIL_UNIFIED_FORCE=1` (`typed.py`) | AIL `ail-py` default / forced |
|---|---|---|---|---|
| `huge_token` | exit 2, no stdout | exit 2, no stdout | exit 2, no stdout | exit 2, no stdout (both) |
| valid 2 x 3 | `dist 3 seen 6` / `total 3`, exit 0 | same | same | same (both) |
| full perf input | 405 bytes, exit 0 | match | match | match |

`AIL_UNIFIED_FORCE=1` forces the general path, so a `--strict` build is refused by name ("not in the
subset: general path explicitly requested"); the forced-unified probes were therefore built without
`--strict`. It matches the reference on the valid case, the huge token and the full perf input.

## Reproduce

    ulimit -v 1500000
    python3 lab/compare_cand/run.py --task grid_bfs --out /tmp/r2.json \
        --langs ail,ail-py,c,rust,go,python
    mkdir -p /tmp/gb/results2 && cp /tmp/r2.json /tmp/gb/results2/result-grid_bfs.json
    python3 lab/compare/merge.py /tmp/gb/results2 --json /tmp/gb/merged2.json

`run.py --task grid_bfs --smoke --out /tmp/r.json --langs python` checks the plumbing on the first
public case and also runs all nine public and hidden cases.
