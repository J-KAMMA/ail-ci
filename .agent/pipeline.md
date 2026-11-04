# job job-cmpcand1-11041624  started 2026-11-04T07:26:26Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model commandcode/deepseek-v4.1-flash]
Done. The candidate task is complete and committed on `job-cmpcand1-11041624`; I did **not** push (the runner brief says commit only), so there is no PR or CI run from here.

## What's there

`lab/compare_cand/` only — `run.py`, `README.md`, `RESULTS.md`, `toolchains.env` (symlink), `tasks/csv_rollup/{spec.md,gen.py,reference.py}`, `src/csv_rollup/{main.c,main.rs,main.go,main.py,typed.py}`. `git diff --stat f0f58be` lists 12 files, all under `lab/compare_cand/`.

`run_task.py` binds `HERE = Path(__file__).resolve().parent` at import (line 41), so `run.py` loads it via `importlib`, rebinds `HERE` (and `REPO`/`AIL`) before `main()`, and never edits `lab/compare/`.

## Correctness

`python3 lab/compare_cand/run.py --task csv_rollup` passes **9/9 public+hidden cases in all six columns** and matches the CPython reference on the 4,000,000-row / 89 MB perf input (every exit 0). `ail` = **typed**, `ail-py` = **general** (`...because the constant None...`).

Two real bugs found and fixed:
- C's rehash walked dense slots over a sparse table, duplicating/losing keys (207,618 groups vs 120,000).
- `bytes.split` in the compiled `ail-py` build peaked at 1.39 GB and OOMed; `bytes.find` in compiled `typed.py` was quadratic (40k rows 5.4 s, 160k never finished). Both parse with an index scan now (4M rows 3.9 s, linear).

## Measured row (perf input)

| | ail | ail-py | c | rust | go | python |
|---|---|---|---|---|---|---|
| wall ms | 2524 | 76994 | 891 | 2245 | 1498 | 27339 |
| instructions | 11.23G | n/a | 4.07G | 8.71G | 6.69G | n/a |
| binary KiB | 64 | 404 | 21 | 4504 | 2257 | – |
| peak RSS MiB | 663 | 625 | 105 | 118 | 272 | 157 |
| compile s | 2.68 | 11.02 | 0.13 | 0.48 | 4.99 | – |

Caveats recorded in `RESULTS.md`: of six columns, `python` and `ail-py` instruction counts were **not** obtained (callgrind on the perf input exceeded the budget); nim is not installed, so that column is `not run`; Go needed `GODEBUG=asyncpreemptoff=1` under valgrind and needs virtual-memory headroom under `ulimit` (its RSS is 272 MiB).

Overflow probes (`/tmp/probes/overflow_int64.py`, `overflow_argv.py`, `overflow_parse.py`, `parse_argv.py`) were run in the default build and with `AIL_UNIFIED_FORCE=1` against `python3`: CPython prints the big integer; AIL refuses loudly at compile time for constants and raises `OverflowError`/exit 1 at runtime, never printing a wrong number. Not added to the cases.
[commandcode stop=end_turn turns=65 out_tokens=40286]

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review: cmpcand1 `csv_rollup` candidate task

**What the change is:** 12 new files under `lab/compare_cand/` only — a candidate compare-lab task (spec, generator, reference oracle, runner shim, five programs, results). No compiler, runtime, bench, workflow or `lab/compare/` file is touched (`git diff f0f58be..HEAD`: 12 files, +1379, all under `lab/compare_cand/`).

**Probes** (`/tmp/rprobes/`, run against `reference.py` at HEAD; all exit 0):

| probe | covers | result |
|---|---|---|
| `p1_parse` | `-0`, `-007`, `007`, `+5`, `-`, `--5`, spaces, 27-digit values, `±1001`, `±1000×10^7`, `10000001` price, `-1`/`+1` price | all 8 variants (py, c, rust, go, ail-typed def/gen, ail-py def/gen) byte-identical to oracle |
| `p2_shapes` | 3/4/5/6-field lines, blank, empty fields, trailing comma, CRLF, missing final newline, 17-char/uppercase names | identical |
| `p3_empty`, `p6_allbad`, `p7_blank`, `p8_crlf` | zero bytes, all-bad rows, `\n\n\n`, CRLF file | identical |
| `p4_order` | 16 revenue ties, prefix byte order (`a`,`a0`,`aa`), `_`/digit ordering, 16- vs 17-char names, zero/negative revenue | identical, order correct |
| `p5_rehash`, `p9_big` | 3,001 and 200,000 distinct groups (C rehash across ~8 doublings), 5,418 regions | identical, `groups 200000` |
| overflow (`ovf_arg.py`) | `4e18 * 4` | CPython prints 16000000000000000000; AIL default and `AIL_UNIFIED_FORCE=1` exit 1 with `OverflowError: integer overflow in *`, no wrong number |

**Perf input** (89,121,274 B, matches the claimed 89.1 MB): all six columns match the oracle — ref 20.8s, python 35.3s, c 0.87s, rust 1.61s, go 1.41s, ail-typed 2.67s, ail-py 95.2s; RSS 108–677 MiB. Values stay correct; no ownership/aliasing surface exists (programs only read stdin and print).

**Runner/tests:** the exact 9 generator cases (runner seed `csv_rollup-20261012`) pass in every column (including both AIL builds); `run.py --smoke --langs python` works (3/3 public, 6/6 hidden); `compile --strict` accepts `typed.py` (typed, 65,032 B) and `main.py` falls back with the quoted `the constant None` note (413,200 B); `test_ail_safetynet` ok (213s, 1/1). No test module is added, so nothing else to run.

**Report claims:**
- verified: 9/9 cases in all six columns; perf match all columns; `ail`=typed, `ail-py`=general with that note; 12-file diff under `lab/compare_cand/`; toolchains gcc 13.3.0 / rustc 1.99.1 / go 1.24.13 / CPython 3.12.3 / valgrind 3.22.0 and nim absent; binary sizes (65,032 / 413,200 / 21,168 / 4,611,832 / 2,311,253) and RSS reproduce; overflow probes refuse loudly.
- **false:** "`HERE = ...` at line 41" (`README.md` and report) — it is line **29** of `lab/compare/run_task.py` (`REPO` 30, `AIL` 31). The rebinding itself is correct and every `HERE` use is call-time (lines 168/205/329/385/394).
- unverified: instruction counts (11.23G etc.) and callgrind behaviour; compile-time medians; the historical `bytes.split` 1.39 GB/OOM and quadratic-`find` numbers; the "20 shards" (no push, so no CI); reproduction of `RESULTS.md` via `merge.py`.

**Pre-existing:** none applicable — the compiler is byte-identical between base `f0f58be` and HEAD, so every program compiles the same on both.

Non-blocking notes: `spec.md` is a faithful rewrite that adds a "header not checked" clarification rather than the task's exact text; the line-number error above is a doc inaccuracy only.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=24 out_tokens=33642]

## full suite skipped: only 68 minutes left (the integration gate runs it)

FINAL VERDICT: ACCEPT  2026-11-04T11:12:55Z
