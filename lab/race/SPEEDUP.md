# par_collatz: AIL's wall-time speedup from 1 to 4 threads, against C, Rust and Go

Task: `lab/compare_par/tasks/par_collatz` (spec, `gen.py`, `reference.py`); sources:
`lab/compare_par/src/par_collatz/{typed.py,main.py,main.c,main.rs,main.go}`. Perf input
`N = 7,000,000`, `W` workers, `W` = 1, 2, 4. One line of output: largest step count, smallest `n`
that reaches it, sum of all step counts.

Per owner decision D5 the task lives in `lab/compare_par/`, outside `lab/compare/src`, so the daily
compare-lab table stays at "x/10". `lab/compare/run_task.py` finds a task in either directory and
reads its `threads` field (`threads: N` in `spec.md`, else `THREADS` in `gen.py`) to set
`AIL_THREADS`; the ten existing tasks have no such field and their build commands are unchanged
(checked byte for byte, before/after).

## Wall time (ms, median of 3 runs; 4 vCPU runner, load average 1.86-2.13)

| language    | W=1    | W=2    | W=4    | speedup 1→4 |
|-------------|-------:|-------:|-------:|------------:|
| AIL         | 1270.6 |  885.7 |  602.6 | **2.11x**   |
| AIL (py src)| 1261.9 |  886.9 |  584.1 | 2.16x       |
| C           | 1082.0 |  701.6 |  527.8 | 2.05x       |
| Rust        |  923.5 |  588.4 |  424.6 | 2.18x       |
| Go          | 1545.8 | 1184.4 |  813.6 | 1.90x       |
| CPython     | n/a    | n/a    | n/a    | n/a (see below) |

**AIL at 4 threads is 1.42x Rust's wall time** (602.6 / 424.6 ms), and 1.38x at W=1
(1270.6 / 923.5). Both are inside the 1.5x target. AIL's own speedup is **2.11x**, below the 2.5x
target; where the rest goes is below.

CPython cannot run the perf input: `ThreadPoolExecutor.map` submits all N items eagerly, one
`Future` each (~800 B), so N=7,000,000 needs more than 5.6 GiB. At a 6 GB `ulimit -v` it reached
5,618,884 KiB RSS and raised `MemoryError` after 77.7 s at W=4; under the 1.5 GB heavy-run cap it
fails at once. Its public and hidden cases (all small) match the reference.

## Where the time goes (AIL, W=4, 602.6 ms)

| piece                                  | time      | share |
|----------------------------------------|----------:|------:|
| sequential tail (reduce 7e6 entries)   | 11.0 ms   | 1.8%  |
| thread start + process (N=1000, W=4)   | ~1.7 ms   | 0.3%  |
| chunk arithmetic (W divides)           | <0.1 ms   | ~0%   |
| parallel compute                       | ~590 ms   | 98%   |

- The results array is 7e6 x 8 B = 56 MB; it is allocated before the fork-join and filled by the
  workers, not a serial stage (peak RSS 119 MiB includes the runtime).
- The parallel part scales 2.13x of the 4x ideal (53% efficiency). The runner is the ceiling: it
  has 4 vCPUs and ran at load average ~2 (other agents), and C (2.05x), Rust (2.18x) and Go (1.90x)
  hit the same wall. AIL is not losing ground relative to Rust (1.38x at W=1, 1.42x at W=4).
- User CPU at W=4 grows from 1.23 s to 1.62 s for AIL, but C grows 1.07 -> 1.44 s and Rust
  0.90 -> 1.17 s the same way: that is the lower effective clock under contention, not added work.
  The instruction count says the same (below).

## Instructions (callgrind Ir, user space; `tools/icount.c` needs perf_event, which this runner denies)

| AIL            | instructions  |
|----------------|--------------:|
| W=1            | 8,854,987,984 |
| W=4            | 8,855,009,763 |
| growth         | +21,779 (**+0.00025%**, limit 5%) |

The threads add no work. (The `[0] * N` result list and the reduce are in both counts; the W=4
count includes the worker start/join.)

## Size, memory, build

Perf-size peak RSS at W=4; build numbers are cold builds, median of 3 (`run_task.py --smoke`).

| language    | peak RSS (W=4) | binary (B) | stripped (B) | compile (s) | build disk (KiB) |
|-------------|---------------:|-----------:|-------------:|------------:|-----------------:|
| AIL         | 121,960 KiB    | 36,280     | 31,016       | 0.944       | 144              |
| AIL (py src)| 121,944 KiB    | 40,592     | 35,112       | 0.854       | 156              |
| C           |  29,092 KiB    | 16,280     | 14,472       | 0.053       | 16               |
| Rust        |  56,732 KiB    | 3,889,104  | 379,376      | 0.213       | 3,800            |
| Go          |  56,924 KiB    | 2,391,212  | 1,554,648    | 4.209       | 37,800           |
| CPython     | >5.6 GiB       | -          | -            | -           | -                |

AIL's RSS is the int64 result list (56 MB) plus the runtime; C stores step counts as int32 (28 MB),
Rust and Go as int64 (56 MB).

## Verification

- All 21 public + hidden cases (`N=1`, `W > N`, `W=1`, `W=N`, odd/even `W`, up to `N=200000`) match
  `reference.py` in AIL, AIL-from-`main.py`, C, Rust, Go and CPython: 0 failures, 4/4 public and
  17/17 hidden for every column.
- `typed.py` builds on the typed parallel path: `compile --strict` accepts it and the default build
  prints no `general path` note (empty stderr). `main.py` compiled by AIL is typed too, so both AIL
  columns run the lock-free PAR runtime.
- `run_task.py --task par_collatz --smoke` passes for every installed language.
- Not verified: a full `run_task.py` perf run (CPython's callgrind would hit the 7000 s timeout and
  CPython itself needs >5.6 GiB at this N), and the CI shards (the standing rules for this job
  forbid pushing, so no `compare-lab` run was started; nothing under `AIL_CURRENT` changed).

## Notes

- Nim is left out: `nim` is not installed on this runner (the workflow installs the pinned 2.2.12),
  so a threads build without new flags could not be checked.
- The `compare-lab` workflow's plan step enumerates `lab/compare/src`, so
  `gh workflow run compare-lab -f tasks='par_collatz'` would be rejected while the task stays in
  `lab/compare_par` (D5). Running it needs either a workflow input for a second directory or the
  task moved into `lab/compare/src` — which would add the 11th row the owner deferred. The numbers
  above come from this 4-vCPU runner with the same build commands `run_task.py` uses.
