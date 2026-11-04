# job job-cmpjoin1-11042326  started 2026-11-04T14:33:05Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Both commits are on `job-cmpjoin1-11042326`; I did not push (the environment section says commit only), so no PR/CI was opened.

## What I added (9 new files, `git diff --stat 1f15d31`)

`lab/compare_cand/tasks/tsv_join/{spec.md,gen.py,reference.py}` and
`lab/compare_cand/src/tsv_join/{main.c,main.rs,main.go,main.py,typed.py}`, plus `RESULTS-tsv_join.md`.

## Results

- **All 9 public+hidden cases and the 4,000,000-order perf input match CPython** in `ail`, `ail-py`, `c`, `rust`, `go`, `python` (exit 0).
- AIL paths: `typed.py` → **typed**; `main.py` → **general** (`fields returns a tuple on one path and a single value on another`).
- Measured row (99.9 MB input, commit `3357c8b`):

| | AIL | AIL(py) | C | Rust | Go | Python |
|---|---|---|---|---|---|---|
| wall ms | 1146 | 107656 | 700 | 1929 | 2161 | 32497 |
| instructions | 6.42G | n/a | 3.10G | 5.82G | 15.11G | n/a |
| binary KiB | 89 | 424 | 21 | 13003 | 2241 | – |
| peak RSS MiB | 380.4 | 1026.4 | 129.5 | 149.7 | 289.6 | 236.6 |
| compile s | 4.39 | 14.59 | 0.16 | 1.01 | 5.66 | – |

- **int64 probe** (`/tmp/probes/join_sum_overflow.py`, sum 1e19): CPython prints `10000000000000000000`; AIL default and `AIL_UNIFIED_FORCE=1` both stop with `OverflowError`, exit 1, no stdout.

## Caveats

- `nim` is not installed and has no source: not run.
- `rustc` existed only as a broken rustup shim; I installed apt rustc **1.75.0** (pinned 1.99.1 unavailable). Program is std-only.
- Go aborts (exit 2) under a 1.5 GB *virtual* cap, so the final combined run used 4 GB; the earlier 1.5 GB run matched every other column with the same RSS values. This is documented in `RESULTS-tsv_join.md`.
- `perf_event_open` is denied; instructions came from valgrind callgrind (Python/AIL-py too slow to count, `n/a`).
- Required tests pass: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.
[commandcode stop=end_turn turns=57 out_tokens=54693]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: cmpjoin1 (`tsv_join` candidate task)

**What the change really does:** adds a new compare-lab candidate (spec, generator, CPython oracle) and six hand-written implementations for it; it touches no compiler, runtime, or bench code (`git diff work..HEAD -- AIL_CURRENT tools packaging` is empty, 9 new files, second commit only edits RESULTS).

**Probes** (`/tmp/rprobes`, reference vs 6 programs = `main.py`, `typed.py` AIL build, `main.py` AIL build, C, Rust, Go; all byte-identical, exit 0):

| probe | boundary |
|---|---|
| p1/p2/p9/p15/p17 | no `#orders`; `#orders` before `#users`; empty sections; `#orders` at EOF; `#users` only |
| p3 | CRLF (`#users\r`) → zero report, as in CPython |
| p4 | junk and `\t\t` lines before `#users` not counted |
| p5/p16/p18 | duplicate ids incl. `0001`, empty/extra fields, 4–5 fields, tab-only lines |
| p6 | ids 0/2000000000/2000000001, 23-digit numbers, amount 100000000/100000001, `-1`, `+5` |
| p7 | 12-way amount ties, top-10 cut, zero-amount matched user |
| p8 | country tie by byte order; second `#orders` and `#users` in orders section → bad |
| p10/p14 | name 24/25 chars, empty name, all-space names |
| p13 | zero-amount orders: country and user still printed |
| fuzz0–2 | 2.4k users / 18k orders with 2k bad lines, hash-table growth |
| perf.tsv | 300,000 users, 4,000,000 orders, 60 countries, 99,904,669 B — all six match |
| unified-force | `AIL_UNIFIED_FORCE=1` builds of both AIL programs match on fuzz/edges/perf |

Spot-checked outputs follow the spec (p16 `bad 4`, p7 top-10 by id, p8 `ZZ` before `AA`/`MM` on equal sums).

**Tests:** no test module was added/edited; `python3 ../tools/par_check.py -j 2 test_ail_safetynet` → `ok ... 0 failed` (173 s). `tools/update_manifest.py --check` → 0.

**Report claims:**
- 9 new files, allowed list only — **verified**
- 9/9 public+hidden in all six columns — **verified** (run.py smoke: 3/3, 6/6 each)
- perf input 300k/4M/60cc matches in all six — **verified**
- `typed.py` typed, `main.py` general with the quoted note — **verified** (run.py `path`, stderr note)
- wall/RSS/binary numbers — **verified** within noise (AIL 1.05 s/389 MB, C 0.67/132, Rust 1.77/153, Go 2.00/362, Py 31.5/242, AIL-py 105.4/1026; binaries 90928/434240/21416/13315512/2294441 B)
- instructions C 3.10G, AIL 6.42G — **verified** exactly by callgrind; Rust/Go counts **unverified**
- int64 probe — **verified** exactly: CPython `10000000000000000000` exit 0; AIL default and `AIL_UNIFIED_FORCE=1` both `OverflowError ... in +`, exit 1, no stdout
- `nim` missing/no source — **verified**; rustc only a broken shim, `/usr/bin/rustc` 1.75.0 — **verified**
- Go exit 2 under a 1.5 GB virtual cap — **verified on perf input** (0.17 s, exit 2); a tiny input does run under the cap
- "not pushed, no PR" — **verified** (`origin/job-cmpjoin1-11042326` still at `1f15d31`)
- `test_ail_files`, `test_ail_corpus_findings3` pass — **unverified** (not re-run; untouched by the diff)
- 20 shards — **unverified** (nothing pushed, per the environment rule)

**Pre-existing:** none — the diff changes no compiler/runtime file, so no base build comparison applies.

**Unverified:** Rust/Go instruction counts; the historical 1.5 GB combined run; the shard checks.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=27 out_tokens=34636]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T16:52:56Z
