# text_wrap: measured results

- Date: 2026-11-05 (UTC)
- Commit: `ee65d50` (`job-cmpwrap1-11060645`; the result JSON records the same `head`)
- Runner: GitHub Actions, Linux 7.0.0-1017-azure, 4 CPUs, image `20261101.360.1` (shared host,
  so wall times carry noise; instruction counts would not)
- Toolchains: gcc 13.3.0, rustc 1.99.1, go 1.24.13, CPython 3.12.3. `nim` is not installed and
  there is no `main.nim`, so the Nim column is `not run`. `valgrind` is not installed
  (`apt` is not available to this user) and `perf_event_open` is denied
  (`kernel.perf_event_paranoid=4`, `EACCES`), so the instruction counts were **not measured**;
  those cells are `n/a` (see the notes).
- Task: `tasks/text_wrap` (spec, generator, reference oracle), perf input 62,924,583 bytes
  (62.9 MB: 389,281 lines, 9,044,100 words).
- Result: every program matches the CPython reference on all 3 public and 6 hidden cases and on the
  perf input, exit status 0.

## The task

`prog < input`. Line 1 is the width `W` (an int in 10..200); the rest is ASCII text. Paragraphs are
separated by one or more empty lines (a line that is empty or only spaces); words are maximal runs of
bytes other than space, tab and newline. Each paragraph is wrapped greedily (words joined by one
space while the line stays at most `W`; a word longer than `W` goes alone). The wrapped text is not
printed; instead the program prints `paragraphs P lines L words N longest K hash H`, where the hash
is `h = (h * 131 + byte) % 1000000007` over the output (lines joined with `\n`, paragraphs separated
by one empty line, no final newline). No words prints all zeros; a bad first line exits 2 with
nothing on stdout.

## Column paths

- `ail` (`typed.py`): **typed path** (`compile --strict` accepts it; the default build produces the
  same binary). No fallback note.
- `ail-py` (`main.py`): **typed path** as well. The plain CPython source is fully typable here, so
  the default build prints no `note: ... built on the general path ...`; there is no fallback.
- `c`, `rust`, `go`, `python`: no AIL path.

`typed.py` and `main.py` run the same one-pass algorithm and differ only in spelling:

- `typed.py` is annotated (`def main() -> int`, the module constant `MOD: int`) and reads stdin with
  `ail`'s `read_stdin_bytes`, then prints the one result line with an f-string.
- `main.py` is unannotated, reads `sys.stdin.buffer.read()`, and writes with
  `sys.stdout.write("...%d...")`.

Both scan the raw buffer by index (no `bytes.split`), keep only integers as state, and feed the
running hash each output byte (a paragraph separator, a line separator, a space, or a word byte) as
soon as the greedy wrap decides it, so no output line is ever buffered. `main.c`, `main.rs` and
`main.go` are the same state machine over the raw stdin buffer with `int64` counters.

## Table

The table below is the output of `python3 lab/compare/merge.py /tmp/cand-results` on the one result
JSON. `nim` was not run (no toolchain, no source), so its cells read `not run`. The instructions row
is all `n/a` because neither counter was available (see the notes); every other metric was measured
on this runner.

```
# compare-lab: AIL against C, Rust, Go, Nim and Python

AIL commit `ee65d50`; 1 tasks; instruction counts by `none`; smoke run: no.
Every program was run on the same input and its stdout and exit code compared with the CPython `reference.py` of the task. Ratios are AIL / best other language for that row (below 1.00: AIL is better, all metrics are lower-is-better). Best-other covers C, Rust, Go, Nim and Python, and only programs whose output matched.

### Status: output vs the CPython reference, and AIL path

| task | input | AIL | AIL (py src) | C | Rust | Go | Nim | Python | AIL path | AIL(py) path |
|---|---|---|---|---|---|---|---|---|---|---|
| text_wrap | 62.9 MB | match | match | match | match | match | not run | match | typed | typed |

### Correctness: public + hidden cases matching the CPython reference (passed/total)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python |
|---|---|---|---|---|---|---|---|
| text_wrap | 9/9 | 9/9 | 9/9 | 9/9 | 9/9 | not run | 9/9 |

### Scorecard: AIL vs the best other language per column (W = lower than every other, L = not)

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| text_wrap | typed | 9/9 | - | W 1.00x | L 1.34x | L 13.23x | L 6.50x | W 0.99x |
| **wins** | | | **0/0** | **1/1** | **0/1** | **0/1** | **0/1** | **1/1** |

Where AIL loses: text_wrap binary 1.34x; text_wrap compile 13.23x; text_wrap disk 6.50x

### Scorecard: AIL (py src) vs the best other language per column (W = lower than every other, L = not)

| task | path | cases | instr | RSS | binary | compile | disk | wall |
|---|---|---|---|---|---|---|---|---|
| text_wrap | typed | 9/9 | - | W 1.00x | L 1.36x | L 13.77x | L 6.50x | L 1.05x |
| **wins** | | | **0/0** | **1/1** | **0/1** | **0/1** | **0/1** | **0/1** |

Where AIL (py src) loses: text_wrap binary 1.36x; text_wrap compile 13.77x; text_wrap disk 6.50x; text_wrap wall 1.05x

### Instructions (user space)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| text_wrap | n/a | n/a | n/a | n/a | n/a | not run | n/a | - | - | - |
| **geomean** |  |  |  |  |  |  |  |  | - | - |

### Peak RSS (MiB, /usr/bin/time -v)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| text_wrap | 61.4 | 61.4 | 61.5 | 61.9 | 119.9 | not run | 70.4 | 61.5 (C) | 1.00x | 1.00x |
| **geomean** |  |  |  |  |  |  |  |  | **1.00x** (n=1) | **1.00x** (n=1) |

### Binary size (KiB, as built)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| text_wrap | 21 | 22 | 16 | 4444 | 2191 | not run | - | 16 (C) | 1.34x | 1.36x |
| **geomean** |  |  |  |  |  |  |  |  | **1.34x** (n=1) | **1.36x** (n=1) |

### Compile time (s, median of 3 cold builds)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| text_wrap | 0.86 | 0.90 | 0.07 | 0.10 | 4.21 | not run | - | 0.07 (C) | 13.23x | 13.77x |
| **geomean** |  |  |  |  |  |  |  |  | **13.23x** (n=1) | **13.77x** (n=1) |

### Build disk (MiB, fresh build dir with its caches)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| text_wrap | 0.10 | 0.10 | 0.02 | 4.34 | 35.26 | not run | - | 0.02 (C) | 6.50x | 6.50x |
| **geomean** |  |  |  |  |  |  |  |  | **6.50x** (n=1) | **6.50x** (n=1) |

### Wall time (ms, median of 5 timed runs of the perf input)

| task | AIL | AIL (py src) | C | Rust | Go | Nim | Python | best other | AIL / best | AIL(py) / best |
|---|---|---|---|---|---|---|---|---|---|---|
| text_wrap | 319 | 339 | 322 | 342 | 473 | not run | 12621 | 322 (C) | 0.99x | 1.05x |
| **geomean** |  |  |  |  |  |  |  |  | **0.99x** (n=1) | **1.05x** (n=1) |

### Toolchain install size (KiB, `du -sk`, once)

| language | KiB |
|---|---:|
| C | 124,048 |
| Rust | 606,968 |
| Go | 293,412 |
| Python | 62,820 |
| AIL | 42,680 |

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
```

## Notes on the measurement

- Instructions: this runner exposes no hardware counter (`/proc/sys/kernel/perf_event_paranoid` is
  `4`; `tools/icount.c` exits 1 with `perf_event_open: Permission denied`), and `valgrind` is not
  installed and cannot be installed (the user is uid 1001, no `apt` lock). So the whole instructions
  row is `n/a`: not measured, not mismatched. Every other column was measured on this runner.
- The input is 62.9 MB and every column holds the whole buffer plus the running state; the observed
  peak RSS is therefore dominated by the input (C 61.5 MiB, AIL 61.4 MiB, Python 70.4 MiB). Go's
  runtime reserves more (119.9 MiB). All six programs stayed far under the 1.5 GB cap
  (`ulimit -v 1500000` was set for the whole run, and every build and timed run succeeded).
- `ail` and `ail-py` both build on the typed path here, so there is no fallback note to quote. The
  `ail-py` column is the plain CPython spelling compiled by AIL; that it is typable is a property of
  the source, not a change to it.
- Wall time on this shared host has noise; AIL 319 ms vs C 322 ms is a tie within that noise. The
  compile-time ratio (13x over C) is the real loss: AIL's compiler is a Python program, and even
  0.86 s is a full front-end plus a C compile. Binary size and build disk follow from that.

## Behaviour checks (outside the cases)

- The oracle `reference.py` was checked against an independent naive implementation (split the text
  into lines, group paragraphs, split words, wrap with a list of lines, hash the joined output) on
  the 9 generator cases plus 6,000 fuzz inputs. The fuzz covers widths 10..200 and the invalid
  widths 0, 5, 300, first lines `""`, `abc`, `0010`, `+20`, `200 `, `9999`, `020`, a missing first
  newline, empty bodies, CR bytes, tabs, runs of spaces, and inputs with no words. All 6,009
  comparisons matched (stdout and exit status).
- The six programs were then compared against `reference.py` on every public and hidden case:
  3/3 public and 6/6 hidden in all six columns (the `cases_public` / `cases_hidden` cells in the
  JSON), including the `bad_width` public case, which must exit 2 with empty stdout.
- All counters are `int64`: the width is at most 3 digits, `words`/`lines`/`paragraphs`/`longest`
  are bounded by the input size, and the hash stays below 1,000,000,007 before each `* 131 + byte`.
  No value read from the text enters an integer except the width; no overflow is reachable.

## Reproduce

    ulimit -v 1500000
    python3 lab/compare_cand/run.py --task text_wrap --out /tmp/r.json \
        --langs ail,ail-py,c,rust,go,python
    mkdir -p /tmp/cand-results && cp /tmp/r.json /tmp/cand-results/result-text_wrap.json
    python3 lab/compare/merge.py /tmp/cand-results --json /tmp/cand.json
