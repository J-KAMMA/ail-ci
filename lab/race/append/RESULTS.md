# D3: `out.append(v)` in a parallel body (fbpmap3)

Measured by `python3 lab/race/append/run.py` on a 4-vCPU GitHub Actions runner, CPython 3.12.3 /
the default AIL build. Each probe is one source built twice: with `par_range` (the typed, lock-free
parallel path) and with the `range` it stands for (the sequential twin). Both are run at
`AIL_THREADS` 1, 2, 4 and 16, three runs each, with `AIL_PAR_SCHED` unset and with `guided`.
`match` means stdout and the exit status agree; the exception probe also compares the last stderr
line.

## Probes

| probe | shape | verdict |
|---|---|---|
| p01_conditional.py | `if/else` around the append | match |
| p02_two_appends.py | two unconditional appends, a third conditional | match |
| p03_str.py | `list[str]` appends (`ail_slist`) | match |
| p04_exception.py | raises at i == 37 after appending | match |
| p05_empty.py | `par_range(0, 0)`, `out` already holds `[7, 8]` | match |
| p06_more_workers.py | 10 items at 16 threads (one item per block) | match |
| p07_sixteen.py | 1024 items, all four thread counts | match |
| p08_guided.py | heavy Collatz body, `AIL_PAR_SCHED=guided` | match |
| p09_float.py | `list[float]` appends (`ail_flist`) | match |

All nine probes match at every thread count, three runs each, with and without the guided
schedule. The two extra shapes (`p09_float`, and `p08` at the guided block sizes) cover the other
element kinds and variable block sizes.

## Exception semantics

`p04_exception.py` appends `i` and then raises `ZeroDivisionError` at `i == 37`. Both builds exit 1
and print the same (empty) stdout, and the last stderr line is the same
`ZeroDivisionError: integer division or modulo by zero` at every thread count. The runtime joins the
buffers **before** re-raising: every block before the failing one, plus the failing block's buffer up
to the raise, and nothing after -- the state the sequential loop leaves.

A `try` cannot wrap the loop in the typed build (`parallel for cannot be inside try; write instead:
put the loop in its own fn`, so that probe runs on the general path under the lock, exactly as
before this job). `p04` therefore observes the state through the exception the runtime raises, not
through a caught exception; the join-before-raise order is the same code path either way.

## Speed and peak RSS (p10, the append variant of `par_collatz`)

`p10_collatz_append.py` keeps `n` whose step count is odd and appends it, instead of writing into
`r[i]`. Input `4000000 4`; median of three runs; peak RSS from `/usr/bin/time -v`
("Maximum resident set size").

| build | threads | wall | peak RSS |
|---|---:|---:|---:|
| sequential (`range` twin) | 1 | 0.735 s | 18.1 MB |
| typed parallel | 1 | 0.738 s | 34.3 MB |
| typed parallel | 4 | 0.278 s | 35.1 MB |

4-thread speedup over the sequential build: **2.64x** (target at least 2x). Peak RSS at 4 threads:
**1.94x** the sequential build's (limit 2x, owner decision 2026-11-06). Output is identical in every
build: `2003705 4014916227594`.

## Refusals kept

`AIL_CURRENT/test_ail_par_append.py`'s `test_refused` checks these are still refused by name:
appending to two lists in one body, any other read of the appended list, a list of objects, and a
body that both reduces (`acc += e`) and appends.

A use of `out` that textually precedes the first append is refused too: `out[i] = v`, `x = out[i]`,
`len(out)` and a bare `out` in any expression. The receiver names are collected from the whole body
before the walk, so walk order does not matter (`parallel._Body.append_names`). Regression probes
(`write before the first append`, `read before the first append`, `len before the first append` in
`test_refused`); before this fix both built and exited 0 with a wrong list (`[0, 10, 0, 1, 2, 3]`
for the write shape, `[7, 8, 107, 108, 100, 100]` for the read shape).

Scope in v1: the Python surface only (`AIL_SURFACE=python`). The AIL surface's `parallel for` keeps
the old refusal (`test_ail_parallel_for`).

## Files

- `lab/race/append/p01..p10*.py`: the probes and the speed load.
- `lab/race/append/run.py`: the runner behind this file.
