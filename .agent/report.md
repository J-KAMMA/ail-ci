# job job-races3-11060456  started 2026-11-05T20:02:18Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Two commits on `job-races3-11060456` (no push, per the standing rules).

**What I built**
- New task `par_collatz`: `N W` on stdin, Collatz step counts for 1..N on W workers, then a sequential reduce. Sources: `typed.py`, `main.py`, `main.c` (pthreads, contiguous chunks), `main.rs` (`std::thread::scope` + `chunks_mut`), `main.go` (goroutines + `WaitGroup`).
- **Placement — deviation from the file list:** the later owner decision D5 says the task must not join the headline table, so it lives in `lab/compare_par/` (not `lab/compare/src/`), and `run_task.py` now finds a task in either directory. The ten existing tasks' build commands are byte-identical before/after (printed and diffed), and none has a `threads` field.
- `threads: 4` in `spec.md` sets `AIL_THREADS`; `gen.py`'s `THREADS` sets the perf input's W. Nim left out: not installed on this runner, so a threads build without new flags could not be checked.

**Results (4-vCPU runner, load ~2)**
- Wall (ms) W=1/2/4: AIL 1270.6/885.7/602.6 → **2.11x**; C 1082/701.6/527.8 → 2.05x; Rust 923.5/588.4/424.6 → 2.18x; Go 1545.8/1184.4/813.6 → 1.90x.
- **AIL / Rust at W=4 = 1.42x** (1.38x at W=1) — inside 1.5x. Speedup is 2.11x, under 2.5x; C, Rust and Go hit the same ceiling, and the sequential tail is 11.0 ms (1.8%), thread start ~1.7 ms, so the loss is CPU contention, not task overhead.
- Instructions (callgrind; perf_event denied): **8,854,987,984 → 8,855,009,763, +0.00025%** (limit 5%).
- Peak RSS W=4: AIL 119 MiB, C 28 MiB, Rust/Go 55 MiB. Compile: AIL 0.94 s, C 0.05 s, Rust 0.21 s, Go 4.21 s.

**Verified**
- All 21 public+hidden cases match `reference.py` in AIL, AIL-from-`main.py`, C, Rust, Go and CPython (4/4 public, 17/17 hidden, 0 failures).
- `typed.py` and `main.py`-via-AIL both build on the typed parallel path: `--strict` accepts, default stderr empty (no `general path` note).
- `test_ail_typed_parallel`: 16/16 pass at baseline; under `ulimit -v 1500000` two TSan tests fail because the sanitizer cannot map its shadow memory (environmental).

**Not done / open**
- CPython cannot run the perf input: eager `executor.map` needs >5.6 GiB at N=7e6 (5,618,884 KiB RSS, `MemoryError` after 77.7 s at a 6 GB cap). Its correctness cases are fine.
- `gh workflow run compare-lab -f tasks='par_collatz'` would be rejected: the workflow's plan step enumerates `lab/compare/src`, and D5 keeps the task out of it; editing the workflow was forbidden. No CI shards were run because pushing is forbidden for this job.
- Merging adds no row to the daily table (still "x/10") thanks to D5.
[commandcode stop=end_turn turns=74 out_tokens=65920]

## review 0
[model commandcode/deepseek-v4.1-flash]
Time check: 20:44, well inside the box. I have enough to report.

## What the change really does
Adds a new compare task `par_collatz` (five sources + spec/gen/reference) under `lab/compare_par/` (not `lab/compare/src/`, per owner decision D5), and teaches `lab/compare/run_task.py` to locate a task in either directory and to read a `threads:`/`THREADS=` field, setting `AIL_THREADS` only when present. No compiler, runtime or test file is touched. This matches the report.

## Probes (all 5 sources vs `reference.py`; rebuilt from source)
| probe (stdin) | result |
|---|---|
| `1 1`, `2 1`, `10 3`, `5 1024`, `1000 4` (no newline), `3 8` | all OK |
| `300001 7` (peak 1.7e10 > 2^32, uneven chunks) | all OK (int64/u64 widths) |
| `100000 1024` (max W) | all OK |
| `3 8 99` (extra token) | reference exit 1; main.py OK; typed/C/Rust/Go run and print `7 3 8` |
| `3` (one token) | reference exit 1; Rust panics exit 101; others exit 1 |
| `0001000 0004` (leading zeros) | all OK except Go (octal: `143 327 26915`) |

The three divergences need invalid or non-canonical input (`spec.md`: "two integers … nothing else"); the produced cases are canonical, and all 21 public+hidden cases match in every column. Not blocking.

## Claims
- 21/21 cases match in ail, ail-py, C, Rust, Go: **verified** (`run_task.py --smoke`, 4/4 + 17/17 each; documented default command exits 0, `nim` build fails gracefully).
- Both AIL columns on typed path (`--strict` accepts, no general-path note): **verified** (`path: typed`).
- Ten existing tasks' build commands unchanged, no `threads` field: **verified** (normalised command lists identical for 5 tasks; `task_threads` → None).
- Speedup 2.11x, AIL/Rust 1.42x: arithmetic **verified**; my own run gives AIL 999→477 ms (**2.09x**) and Rust 922→329 ms, AIL/Rust = **1.45x** — inside 1.5x. Rust reached 2.80x here, so the report's "C/Rust/Go hit the same ceiling" is load-dependent and not robust, but the target ratio holds and the <2.5x explanation is present.
- Instructions +0.00025% via callgrind because `perf_event` is denied: denial **verified** (`icount.c` → "Permission denied"); the counts themselves **unverified**.
- Peak RSS AIL ≈119 MiB, C ≈28 MiB: **verified** (122,016 / 29,092 KiB at N=7e6, W=4).
- COMPILE AIL 0.94 s: **verified** (0.93 s). Nim omitted because not installed: **verified**.
- "test_ail_typed_parallel 16/16 at baseline; two TSan tests fail under ulimit": under `ulimit -v 1500000` I get **14/16**, failing `test_asan_ubsan` and `test_tsan` (shadow-memory mapping) — one ASan, one TSan, so the report's "two TSan" is slightly wrong; environmental, not the change.
- Workflow cannot run it (`plan` step requires `lab/compare/src/$t`, rejects `par_collatz`): **verified**, and the report states it.
- No CI shards run: **verified** (no push).

## Pre-existing
`test_ail_safetynet` fails `S4_generators_gc` (truncated stdout) **identically on `work`** in a `/tmp/base` worktree — not caused by this change (which touches no compiler code).

## Unverified
Full-CPython perf behaviour (MemoryError at ~5.6 GiB), the callgrind instruction counts, and the exact runner wall/RSS medians (only best-of-3 reproduced).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=27 out_tokens=27669]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T21:58:14Z
