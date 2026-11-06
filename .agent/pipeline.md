# job job-devcc1_rr1-11060646  started 2026-11-05T21:46:41Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. `tccprobe1` was present on `origin/integ`, so I ran the measurement.

## devcc1 results (MIR v1.0.0, commit `477d820`, built in `~/scratch/mir`)

| | gcc -O2 | c2m |
|---|---|---|
| (a) generated C accepted | 50/50 | **0/50** (0 compare, 0 corpus) |
| (b) byte-identical stdout/stderr/exit | reference | **0** — none compiled |
| (c) median C-compile | **0.9777 s** | **n/a** (time to first error: 91 ms) |
| (d) median run | 1.234 s compare / 3.7 ms corpus | n/a |

**Buckets (50):** 32 GNU `__typeof__` (the `ail_len_t` typedef, `cruntime.py:199-200`), 13 `__int128` (`cruntime.py:16893`), 5 `__uint128_t` (`cruntime.py:3841-3844`). `wrong output = 0`; no c2m build ever ran. Excerpts: `lab/devcc/fail_1_typeof.txt`, `fail_2_int128.txt`, `fail_3_uint128.txt`.

**Step-1 facts:** c2m has `-ei/-eg/-el/-eb` but **writes no ELF** (`-o` alone writes binary MIR, magic `MIR\xe2`); libc/libm/pthread are resolved by `dlopen`+`dlsym`, and `-lm` fails because `libm.so` is a linker script. `PIPE_CC` receives every gcc-only flag; both `PIPE_CC=tcc` and `PIPE_CC=c2m` exit 3 with no artifact. The CLI only checks the compiler's exit status and never validates the artifact, so a 0-exit wrong/non-executable output would pass silently — demonstrated, though nothing does today.

**Price:** gcc phase 26.0%, Amdahl bound 1.351×; achieved compile ratio undefined (0 builds) → **0% of the bound**. Hypothetically at MIR's claimed 80×, the build would reach 1.345× (99.6% of the bound).

**Recommendation:** no `--cc=mir` yet — c2m cannot produce an executable at all. Prefer tcc for devcc2 (ELF output, 4 locally-fixable constructs, existing 511-case evidence). Refusal lists for both modes are in `RESULTS.md`.

**Verification:** 17/17 probes pass (`/tmp/probes/c2m_limits.py`); required modules run 25 tests OK (`test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`). One general-path case fails only under the 1.5 GB `ulimit` and passes exactly without it.

Committed 3 commits on `job-devcc1_rr1-11060646`, touching only `lab/devcc/`. Per the runner rules I did **not** push, so no PR/CI run was possible.
[commandcode stop=end_turn turns=133 out_tokens=98160]

## review 0
[model commandcode/deepseek-v4.1-flash]
Done. Here's my review.

## What the change really does
Adds `lab/devcc/run.py` (a c2m measurement arm over tccprobe1's 50-program sample), `lab/devcc/RESULTS.md`, and three `fail_*.txt` excerpts. No compiler, runtime, buildcache or default-build file changes. One note: `RESULTS.md` already existed on `work` (devcc2's report); this diff prepends the new report and keeps the old text verbatim as an appendix — the report calls the file "new", the base did not.

## Verified (against `/tmp/devcc.json`, a runs=1 replay, and direct c2m/tcc runs)
- Scope: `git diff --name-only work..HEAD` = 5 files, all `lab/devcc/`.
- Sample: 50 programs, same 40 corpus names in the same order as `lab/tccprobe/RESULTS.md`, same 5 AIL refusals (`g20_020 g14_012 g15_024 g22_034 g15_028`), 45 candidates tried.
- (a) c2m accepted **0/50**: JSON and my replay both give 0 c2m builds, 50 gcc builds.
- Buckets **32 `__typeof__` / 13 `__int128` / 5 `__uint128_t`**, same in replay; emitter lines `cruntime.py:200`, `16893`, `3842` are correct; per-program lists add to 50.
- Numbers match the report exactly: gcc build median 0.9777 s (0.131–17.2), run 1.234 s compare / 3.7 ms corpus, CPU 1.169 s / 2.0 ms, c2m first-error median 91 ms (52.3–256), 50/50 gcc deterministic, 48 single / 2 multi-unit (`g02_002` 2, `g13_038` 3).
- All 10 compare-task build/run times in the table match the JSON.
- MIR v1.0.0 / `477d820e…`; MIT licence; nothing vendored.
- c2m facts: `-o` alone exits 0 writing `MIR\xe2`, `-lm` fails, `__typeof__(x)` fails while `_Generic` alone passes, `_Thread_local`/`__attribute__`/`_Pragma` accepted, `mir-bin-run` runs a `.bmir` in both lazy and interp modes.
- `PIPE_CC` receives the gcc-only flags; a fake compiler that exits 0 and writes junk makes `ail compile` exit 0 and report success (silent-success claim true).
- Worker's `/tmp/probes/c2m_limits.py` re-run: 17/17 pass.
- `test_ail_safetynet` on HEAD: 5 tests OK (275 s). Worker's `/tmp/devcc-tests2.log`: 25 tests OK (skipped=1).

## Nuances / minor inaccuracies (no effect on the result)
- `c2mir-driver.c` citation `import_resolver at :405` is actually `:428`; the std_libs list is `:68-80`.
- The "c2m -v" wording: `c2m -v` alone errors (`No source file`); the version line comes from `c2m -h`.
- The `PIPE_CC` bullet (exit 3, tcc diagnostics swallowed) is true for the general-path program used (e.g. `g01_010`), where `_general_failure` keeps only the first line. On a typed-path program (`g00_000`) the same invocation exits **4** and prints tcc's diagnostics; the report should say which class it observed.

## Pre-existing
None: the diff changes no behaviour, so generated C is unchanged by construction. The devcc2 appendix text is base content.

## Unverified
Run instruction counts (perf `EPERM`, `perf_event_paranoid=4` confirmed); the hypothetical "typedef fix unblocks 32/50"; the multi-unit `-S`+`m2b` combination path (never exercised — 0 builds); the specific `S4_generators_gc` failure under `ulimit -v 1500000` (the suite passes uncapped; I did not reproduce the capped failure).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=40 out_tokens=51281]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T00:12:39Z
