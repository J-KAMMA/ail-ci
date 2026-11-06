# job job-fdinf1-11060756  started 2026-11-05T23:07:03Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Two commits on `job-fdinf1-11060756`; only `lab/infer/` changed.

**Harness (`bench.sh`)** — one command: `bash lab/infer/bench.sh` fetches with `fetch.sh`, builds `gpt2.py` with the default compile command, then runs AIL and `llama-cli` 5× each over `tokens.txt` (llama's prompt text is checked to tokenize to exactly those 64 ids) and prints:

| program | thr | prefill tok/s | decode tok/s | peak RSS | binary |
|---|---|---|---|---|---|
| AIL default build | 1 | 3.84 | 3.79 | 1053 MiB | 111,120 B |
| llama.cpp `llama-cli` | 1 | 462.90 | 33.17 | 417 MiB | 1,898,560 B |
| llama.cpp context row | 4 | 298.70 | 7.91 | 417 MiB | 1,898,560 B |

Prefill **120.5×** slower, decode **8.75×** per forward (AIL 263.7 ms vs 30.15 ms). Greedy ids equalled `ref.py` and llama.cpp on all 5 runs for both thread counts (llama ids recovered via `llama-tokenize` on its generated text, 16 ids every run). The `-t 4` row is noisy and slower than one thread on this runner — labelled context only.

**Profile (`profile.sh`)** — `perf record` is denied here (`perf_event_paranoid=4`), so it uses callgrind on a one-token prompt + 4 decode forwards, minus a load-only run (the loader is 58% of a short run): `linear__irl` 84.40% (matmul with inlined bounds checks and `ck_add`), `memset` 13.65% (zeroed result lists), `memcpy` 1.28% (per-call weight snapshots), then `ck_add`, `py_main`, `ail_flist_get`, `gelu__irl`, `layer_norm__irl`, `__expm1_fma`, `ail_flist_set`. One line each with the follow-up job is in `RESULTS.md`.

Caveats: this runner is ~2.3× slower than infer1's allocation (both programs slowed equally, so ratios hold); the `--debug` line table drifts into the previous function for the first statements of a body, so the source column is anchored at each function's `def` line. I did not push or open the PR — the run instructions say commit on the current branch and do not push.
[commandcode stop=end_turn turns=80 out_tokens=57120]

## review 0
[model commandcode/deepseek-v4.1-flash]
All checks are done. Final report:

## Review: fdinf1 (bench.sh + profile.sh)

**What the change really does:** adds `lab/infer/bench.sh` (5-run AIL-vs-`llama-cli` tok/s table with per-run greedy-id checks), `lab/infer/profile.sh` (callgrind/perf top-10 decode profile, load-only subtracted, mapped to `gpt2.py` def lines), and README/RESULTS sections. No compiler, runtime or benchmark-program file changed: `git diff --stat work..HEAD` = `lab/infer/` only. Matches the report.

**Probes / checks**
- `bench.sh /tmp/ail-infer 5`, full run, exit 0: table printed; 5 AIL runs and 5 llama runs at `-t 1` and `-t 4`, ids equal to `ref.py` on every run (16/16 each); `prompt.txt`→64 ids check passed. `/tmp/rprobes/p1.py` (attrs/dict/list argument) and `p2.py` (int64 boundary): `cmp.sh` both `same stdout`, exit 0; `--debug-dir` C and binary for `p1` identical on HEAD vs `/tmp/base` (compiler untouched).
- `profile.sh /tmp/ail-infer 4`, exit 0: reproduces RESULTS.md exactly — `linear__irl` 84.40%, memset 13.65%, memcpy 1.28%, `ck_add` 0.15%, `py_main` 0.12%, `ail_flist_get` 0.08%, `gelu__irl` 0.08%, `layer_norm__irl` 0.05%, `__expm1_fma` 0.05%, `ail_flist_set` 0.03%; `gpt2.py:73-87/88-98/49-72` match the real `def` lines.
- `test_ail_safetynet`: pass (493 s, 1/1).

**Claims**
- peak RSS 1053 MiB / 417 MiB — verified. Binary 111,120 B / 1,898,560 B — verified.
- "`--strict` and default binaries byte-identical" — verified (same sha256).
- "perf denied, `perf_event_paranoid=4`" — verified (`perf record` and `perf stat` both fail).
- "prefill 120.5×, decode 8.75×" — **unverified, environment-dependent**: my rerun of the same harness gave AIL 352.6 ms/token prefill / 455.7 ms/forward, llama 5.97 / 40.07 ms → 59× prefill, 11.4× decode. AIL and llama are timed in separate blocks, so runner drift biases the ratio (both still show AIL far slower). Not a code defect.
- "loader 58% (`read_f32` 32%, `ail_bytes_get` 19%, memset 7%)" — unverified (script never prints the load profile; my load-only callgrind gives read_f32 61%, `ail_bytes_get` 34%, memset 2.2% of the load-only run).
- Note: RESULTS.md's source column says `runtime (libc)`/`runtime (libm)`, which `profile.sh` prints as plain `runtime` — hand annotation, cosmetic. llama's ids are checked via re-tokenised text, which the report discloses.

**Pre-existing:** none (no compiler/runtime change).

Not checked: absolute timings under the worker's conditions; CI shards (not pushed by design).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=40 out_tokens=28310]

## full suite
test_ail_modules

## suite fix skipped: only 146 minutes left

FINAL VERDICT: FIX  2026-11-06T01:35:40Z
