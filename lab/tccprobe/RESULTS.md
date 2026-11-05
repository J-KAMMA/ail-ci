# tccprobe1 — does the C that AIL emits build and run with tcc?

Measured 2026-11-05 on the 4-core GitHub Actions runner (Ubuntu 24.04).
- tcc: `tcc version 0.9.27 (x86_64 Linux)` (`/usr/bin/tcc`, installed with `sudo apt-get install -y tcc`)
- gcc: `gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`
- python 3.12.3; seed 20261105; 3 build repetitions and 3 run repetitions per program.
- Nothing in the compiler, runtime or default build is changed. Release builds stay on `gcc -O2`.
  Reproduce with `python3 lab/tccprobe/run.py --out /tmp/tccprobe.json` (tcc on PATH).

## The numbers

| | value |
| --- | --- |
| (a) generated C that builds with tcc | **0 of 50** (0 of 10 compare tasks, 0 of 40 corpus programs) |
| (b) of those, byte-identical stdout, stderr and exit status to the gcc -O2 build | **0** — no tcc build reached a run |
| (c) median C-compile wall time | gcc -O2 **1.2416 s**, gcc -O0 **0.4574 s**, tcc **n/a** (no successful build) |
| (d) median run time | tcc **n/a**; gcc -O2 build **1.4678 s** on the compare tasks, **1.4 ms** on the corpus |

Every one of the 50 emitted C files built with `gcc -O2` and with `gcc -O0`, so the reference side is
complete: the sample is not empty, the failure is entirely on tcc's side.

`wrong_output = 0`. No tcc binary ever ran, so the "wrong output is a stop condition" rule did not
trigger, and there is nothing to record under it.

## What the builds are

For each program the C is produced once by

```
python3 AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT --debug-dir DBG      (plus --syntax python for .py)
```

`DBG/program.c` is byte-identical to the translation unit the compiler was handed (verified by
sha256 against a `PIPE_CC` shim: `facf9d98…` both ways on `corpus/gdev/g01_010.py`), and
`DBG/native_report.json` records the exact compiler command line. The three builds are that command
line with only the compiler (and `-O0` replacing `-O2`) changed:

```
gcc -O2   the recorded command line, unchanged           (e.g. -O2 -fno-tree-slp-vectorize -ffp-contract=off
gcc -O0   the same, -O2 -> -O0                            -fopenmp-simd -Werror=implicit-* -fno-asynchronous-unwind-tables … -lm)
tcc       tcc C… -lm                                      (only -I/-D/-L plus the recorded libraries; gcc-only flags dropped)
```

Two general-path programs are built as several translation units (`g02_002`: 2, `g13_038`: 3); there
the `-c` steps and the link are run in sequence and their times summed, exactly as the build does.

Timing: every attempt gets a fresh directory, 3 attempts, median. Runs: 3 executions of the task's
performance input, median; stdout, stderr and exit status compared as bytes against the gcc -O2
build. All 50 gcc -O2 output sets were identical across their three runs (deterministic), and gcc -O0
matched gcc -O2 on 49 of 50 (`scar_life`'s -O0 run did not finish inside the 25 s bound), so the
reference is not hiding undefined behaviour between optimisation levels.

## Failure buckets

tcc stops at its first error, so each program is counted once, under the first construct that stops
it. These are lower bounds on the number of incompatible constructs per file.

| bucket | count | generated C construct | emitted by |
| --- | --- | --- | --- |
| unsupported builtin or intrinsic | 8 | 7 × `__builtin_unreachable()`; 1 × `__int128` | `pkg-v12/cruntime.py:433,4044,4065`; `cruntime.py:3917-3919`, `bigint_obj.py:403-411`; `cruntime.py:29709` |
| attribute or pragma | 19 | `static _Thread_local void *ail__rep_stk[512];` | `pkg-v12/cruntime.py:17245-17246` (also `cruntime.py:30362`, `jsonrt.py:858`) |
| other (tcc parser) | 23 | `ail_stdout_parts((ail_str[]){ir848, ir849}, 2);` — unsized struct-array compound literal built from runtime values | `pkg-v12/pyfunc.py:24481` |
| inline asm | 0 | — | (`cruntime.py:365`, `30715`; `safetyrt.py:1437` exist but were not the first error) |
| link error | 0 | — | (the 7 `__builtin_*` cases fail at the link step, but the cause is the missing builtin) |
| wrong output | 0 | — | — |

Exact diagnostics and one program per bucket: `fail_1_…txt` … `fail_4_…txt` in this directory.

1. **`_Thread_local` (19).** `tcc: ' ;' expected (got "void")` at
   `static _Thread_local void *ail__rep_stk[512];`. tcc 0.9.27 has no thread-local storage at all:
   `static __thread int n;` fails the same way (probe `gnu_thread_kw`). Comes from the recursive
   `repr` stack of the boxed runtime (`cruntime.py:17245`).
2. **Unsized struct-array compound literal with runtime elements (23).** `error: index too large` at
   e.g. `ail_stdout_parts((ail_str[]){ir848, ir849}, 2);`, the print path for an f-string
   (`pyfunc.py:24481`). The boundary, measured with probes: unsized compound literal of a
   **multi-member** struct array from **lvalue** initializers fails; the same with constant
   initializers builds; `(S[2]){a,b}` (sized) builds; a one-member struct builds. So it is tcc's
   size inference for an unsized aggregate literal with non-constant elements, not the initializer
   syntax itself.
3. **`__builtin_unreachable` (7).** tcc compiles the whole file (warning: implicit declaration) and
   fails at link: `tcc: error: undefined symbol '__builtin_unreachable'`. These 7 are the closest to
   a build: the C parses, only the builtin is missing. If it were emitted as something tcc knows,
   those files would link — whether they would then run correctly is unmeasured.
4. **`__int128` (1).** `static __int128 ail_rand_floordiv(__int128 a, __int128 b)` (`cruntime.py:29709`,
   `random.randrange`). tcc has no 128-bit integer type: `' ;' expected (got "ail_rand_floordiv")`.

Timing context for (c): an invocation that ends in a parse error returns after a median of
**13 ms** (range 7.2–30.1 ms, 43 programs); a full parse that then fails to link returns after a
median of **9.9 ms** (7 programs). No successful tcc build exists to compare against gcc's 1.24 s.

## The sample

**10 compare tasks** (`lab/compare/src/<task>/main.ail`), performance input, all built with gcc -O2
and gcc -O0:

| task | gcc -O2 build | gcc -O0 build | gcc -O2 run | tcc first blocker |
| --- | --- | --- | --- | --- |
| berth_sim | 1.62 s | 0.51 s | 2.572 s | compound literal |
| chain_relax | 0.59 s | 0.31 s | 1.268 s | `__builtin_unreachable` |
| echo_pack | 0.55 s | 0.42 s | 1.118 s | compound literal |
| ledger_bin | 1.14 s | 0.56 s | 0.917 s | compound literal |
| rail_transfer | 1.23 s | 0.43 s | 0.114 s | compound literal |
| scar_life | 0.69 s | 0.53 s | 29.804 s | compound literal |
| tally_lang | 1.25 s | 0.61 s | 1.417 s | compound literal |
| term_rank | 1.52 s | 0.63 s | 2.472 s | compound literal |
| ticket_audit | 2.36 s | 0.85 s | 1.970 s | compound literal |
| tree_fold | 1.80 s | 0.74 s | 1.519 s | compound literal |

**40 corpus programs**, chosen as: `corpus/gdev/*.py` sorted, shuffled with
`random.Random(20261105)`, first 40 whose emitted C builds with gcc -O2 (45 candidates tried):

`g01_010 g02_002 g18_038 g25_038 g05_016 g00_004 g03_018 g04_016 g17_002 g04_004 g06_000 g04_038
g17_026 g13_014 g18_006 g19_018 g09_026 g22_022 g13_038 g04_008 g16_004 g00_000 g21_032 g20_000
g09_002 g22_014 g12_038 g09_032 g06_004 g04_034 g03_012 g21_020 g23_028 g03_006 g12_008 g18_016
g23_032 g02_000 g13_018 g25_000`

Emitted C per program: median 330 KB (min 155 KB `g22_022`, max 2.34 MB `g13_038`), 23.0 MB for the
50 together.

Five candidates were refused by AIL and replaced by later ones (they are not part of the 40):
`g20_020` (`urllib.parse.urlsplit` not built), `g14_012` (class attribute `Rectangle.area` not built),
`g15_024` (`traceback` not available), `g22_034` (`int64 literal out of range: 18446744073709551615`),
`g15_028` (`logging` not available).

## What this says and what it does not

- As a **bootstrap seed**, the current generated C is not usable with tcc 0.9.27 without changing
  the emitted C: three constructs (print-path compound literals, the repr stack's `_Thread_local`,
  `__builtin_unreachable`) block every program in this sample, before any question of correctness
  can be asked.
- As a **fast dev-build**, there is nothing to time: gcc -O2's median 1.24 s per program has no tcc
  counterpart because no program builds. tcc's own parse is fast (≈10–13 ms to the first error or to
  the link step on a ~300 KB file), so the open question is compatibility, not speed.
- This measured one tcc version (0.9.27, the Ubuntu package). Nothing here says whether a later tcc
  parses `_Thread_local` or unsized aggregate literals.
- Metric (b) and (d) are vacuously zero/absent rather than "no difference": not one tcc binary ran.

## Probes run

No compiler or runtime behaviour was changed, so there is no language-level probe against CPython;
the probes below check the measurement itself and the tcc claims the report makes.

| probe | what it checks | result |
| --- | --- | --- |
| `/tmp/probes/measure_fidelity.py` | the rebuilt gcc -O2 command has the same flags as `native_report.json`, and its binary prints exactly what a plain `ail compile` binary prints (`g01_010`, `g18_038`) | flags equal, stdout/stderr/exit equal for both |
| `/tmp/probes/tcc_limits.py` (16 cases) | each construct claim and its boundary: `_Thread_local`, `__thread`, `__int128`, `__builtin_*`, `__attribute__((always_inline))`, statement expression, unsized/sized compound literals, constant vs runtime initializers, 1 vs 2 members | all 16 match the report's claims |
| `/tmp/probes/measure_logic.py` | `classify()` maps all four real tcc stderr forms (plus attribute, asm, plain link error) to the right bucket, and the seed picks the same corpus twice | 7/7 classifications, selection stable |
| plain-C tcc hello | the tcc install itself works (not a broken invocation) | builds and runs |

The `bash ~/tools/cmp.sh` loop does not apply here: it compares an AIL program against CPython
after a compiler change, and this job changes neither the compiler nor the runtime.
