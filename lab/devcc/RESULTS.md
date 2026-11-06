# devcc1 — can MIR's c2m compile AIL's generated C, and how fast?

Measured 2026-11-05 on the 4-core GitHub Actions runner (Ubuntu 24.04).
- MIR **v1.0.0**, commit `477d820e7b3054980ea1b936ecb2945c0e6465e8` (`git describe --tags` → `v1.0.0`);
  `c2m version commit=477d820e7b3054980ea1b936ecb2945c0e6465e8`. Built outside the repo in
  `~/scratch/mir` with `git clone --depth=1 --branch v1.0.0 … && make -j2`; MIT licence, nothing vendored.
- gcc `13.3.0`; python 3.12.3; seed 20261105; 3 build repetitions and 3 run repetitions per program.
- Same 50 programs as tccprobe1: the 10 `lab/compare/src/*/main.ail` tasks and the 40 `corpus/gdev`
  programs its seed selects (45 candidates tried, the same 5 refused by AIL/gcc and replaced).
- Nothing in the compiler, runtime or default build is changed. Release and default builds stay on
  gcc `-O2`; c2m is invoked only by this measurement script.
- Reproduce with `python3 lab/devcc/run.py --mir ~/scratch/mir --out /tmp/devcc.json --excerpts lab/devcc`
  (MIR built in `~/scratch/mir`).

## The numbers

| | gcc `-O2` | tcc 0.9.27 (tccprobe1) | **c2m (MIR v1.0.0)** |
| --- | --- | --- | --- |
| (a) generated C the compiler accepts | 50 of 50 | 0 of 50 | **0 of 50** (0 of 10 compare, 0 of 40 corpus) |
| (b) of those, byte-identical stdout, stderr and exit status | 50 of 50 (reference) | 0 — none ran | **0 — none compiled** |
| (c) median C-compile wall time | **0.9777 s** | n/a | **n/a** (no successful build) |
| — median time to the first error | — | 12.7 ms (parse) / 9.2 ms (link) | **91 ms** (52.3–256 ms, 50 programs) |
| (d) median run wall time | 1.234 s compare, 3.7 ms corpus | n/a | **n/a** |
| median run child-CPU time | 1.169 s compare, 2.0 ms corpus | n/a | n/a |

All 50 emitted C files build and run with gcc `-O2` (and every gcc `-O2` output set was identical
across its three runs), so the reference side is complete. `wrong_output = 0`: **no c2m build ever
reached a run**, so the "wrong output is a stop condition" rule did not trigger and there is nothing
to list under it.

**(a)–(d) are therefore zero/vacuous for c2m, not "no difference".** The reference gcc numbers are
from this run; tcc's column is tccprobe1's, measured on the same sample with the same protocol.

Run instructions were **not measurable here**: `tools/icount.c` builds, but `perf_event_open` returns
`EPERM` and `/proc/sys/kernel/perf_event_paranoid` is `4`. Run times are wall medians plus child CPU
medians (less noisy than wall); tccprobe1 likewise reported wall time only. Another job
(`lab/compare_cand`) ran on the same 4-core runner during part of this measurement, so one gcc build
outlier (`g13_038`, 17.2 s) is contention; the medians are robust to it.

## How c2m runs, and what it cannot produce (step 1)

`c2m` **writes no ELF executable**. Its run modes execute C in-process:

| mode | what it does |
| --- | --- |
| `-ei` | interpret the MIR |
| `-eg` | generate machine code, then run (the mode the task names) |
| `-el` | lazily generate machine code, then run |
| `-eb` | lazily generate basic-block code, then run |

`-S` writes textual MIR, `-c` writes **binary MIR** (`-o file` alone also writes binary MIR and exits
0). The file starts with `MIR\xe2`, not `\x7fELF`. It is run with
`~/scratch/mir/mir-bin-run <file.bmir> <argv0> [args…]` (`MIR_TYPE=interp|jit|lazy`, default lazy).
For a single C file, `-c` writes one `.bmir`; a multi-unit build (2 of 50 here: `g02_002` 2 units,
`g13_038` 3 units) is combined by compiling each unit with `-S` to textual MIR, renaming the module
(`M0:` collides otherwise), concatenating, and running `m2b` (stdin→stdout). That combination is what
`run.py` times and runs; it is not a c2m feature but it is the only way to run a multi-unit program
from `.bmir`.

**Library resolution.** c2m `dlopen`s a fixed list of standard libraries and resolves every imported
symbol with `dlsym` at link time (`c2mir/c2mir-driver.c:78-92`, `import_resolver` at :405): on this
host `/lib64/libc.so`, `/lib/x86_64-linux-gnu/libc.so.6`, `/lib64/libm.so.6`,
`/lib/x86_64-linux-gnu/libm.so.6`, `/usr/lib64/libpthread.so.0`,
`/lib/x86_64-linux-gnu/libpthread.so.0`, `/usr/lib/libc.so`. `-l<name>` additionally `dlopen`s
`lib<name>.so` from the `-L` directories. On Ubuntu 24.04 `libm.so` is a GNU ld linker script, so
**`-lm` fails** (`cannot find library libm -- good bye`) even though `sqrt` resolves from the already
preloaded `libm.so.6`. A c2m mapping must drop AIL's `-lm`.

**`PIPE_CC` today** (`buildcache.resolve_compiler`, `buildcache.py:291`; the value is used as one
argv[0]). The argv recorded by a logging shim is exactly:

```
-O2 -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd
-Werror=implicit-function-declaration -Werror=implicit-int -Werror=incompatible-pointer-types
-fno-asynchronous-unwind-tables -o <out> <program.c> -lm
```

So **all gcc-only flags reach `$PIPE_CC`**. One program each:
- `PIPE_CC=tcc` → CLI exit 3, no artifact; only AIL's generic "the C compiler rejected this" is shown;
  tcc's own diagnostics are swallowed.
- `PIPE_CC=<c2m>` → c2m exits on `unknown command line option -fno-tree-slp-vectorize`; CLI exit 3,
  no artifact.

**Can a wrong output pass silently?** The CLI checks only the compiler's exit status and never
inspects or runs the artifact (`pyc._finalize_output` only appends `.exe` on Windows). A compiler that
exits 0 and writes a non-executable or wrong file would be reported as success. Demonstrated:
`c2m -O2 -o OUT prog.c` exits 0 and writes binary MIR (`MIR\xe2`), not an executable. Today both
`PIPE_CC=tcc` and `PIPE_CC=c2m` fail loudly on this sample, so **nothing passes silently here** — but
nothing in the CLI would stop it, and adding `-c` to a c2m wrapper would make `ail compile` report
success for a file that cannot run.

## Failure buckets

c2m compiles the whole translation unit and then links, so each program is counted once under the
first construct that stops it (the first error in file order; c2m's warnings about out-of-range float
literals come first and are ignored). Bucket names follow tccprobe1; `other (tcc parser)` becomes
`other (c2m parser)`.

| bucket | count | generated C construct | emitted by |
| --- | --- | --- | --- |
| other (c2m parser) | **32** (10 compare + 22 corpus) | `typedef __typeof__(_Generic((int64_t)0, long: (long long)0, default: (long)0)) ail_len_t;` — **c2m has no GNU `typeof`/`__typeof__`** (it rejects even `__typeof__(x)`; `_Generic` alone is accepted). The failed typedef leaves `ail_len_t` undefined, so `ail_list` fails and every later `ail_list *` is a syntax error | `AIL_CURRENT/python/pkg-v12/cruntime.py:199-200` |
| unsupported builtin or intrinsic | **13** (corpus) | `__int128 nn = (__int128)n;` in the range-slice path | `AIL_CURRENT/python/pkg-v12/cruntime.py:16893` |
| unsupported builtin or intrinsic | **5** (corpus) | `__uint128_t num, den;` in the 128-bit shift helper | `AIL_CURRENT/python/pkg-v12/cruntime.py:3841-3844` |
| attribute or pragma | 0 | (c2m accepts `_Thread_local` with a warning, and `__attribute__`/`_Pragma`/unknown pragmas) | — |
| inline asm | 0 | (present in the runtime, never the first blocker; c2m would fail at import) | — |
| link error | 0 | — | — |
| no executable output | **50** (all) | c2m writes binary MIR, never ELF; running needs `mir-bin-run` | artefact property of every c2m run |
| wrong output | **0** | — | — |

"No executable output" is a property of every c2m invocation, not a per-program first blocker, so it
is counted once globally and not in the 32+13+5 = 50 per-program buckets.

One excerpt per construct: `fail_1_typeof.txt`, `fail_2_int128.txt`,
`fail_3_uint128.txt`. Programs by construct:

- GNU `__typeof__` (32): all 10 compare tasks; corpus `g18_038 g25_038 g04_016 g17_002 g06_000 g04_038
  g17_026 g19_018 g09_026 g22_022 g13_038 g04_008 g00_000 g09_002 g22_014 g09_032 g06_004 g04_034
  g03_006 g12_008 g18_016 g02_000`.
- `__int128` (13): `g01_010 g02_002 g05_016 g00_004 g04_004 g13_014 g18_006 g16_004 g21_032 g20_000
  g21_020 g23_028 g13_018`.
- `__uint128_t` (5): `g03_018 g12_038 g03_012 g23_032 g25_000`.

The complement is worth noting: c2m accepts two forms tcc 0.9.27 rejects — `_Thread_local` (with a
warning) and an unsized struct-array **declaration** from runtime values — and rejects one tcc accepts,
GNU `__typeof__` (tcc supports it). Both reject `__int128`/`__uint128_t` and an unsized struct-array
**compound literal** from runtime values (`excess elements in scalar initializer`).

## The sample

**10 compare tasks**, performance input, all built and run with gcc `-O2`; every one stops c2m at the
`ail_len_t` typedef:

| task | gcc -O2 build | gcc -O2 run | c2m first blocker |
| --- | --- | --- | --- |
| berth_sim | 1.1959 s | 2.2210 s | GNU `__typeof__` |
| chain_relax | 0.4465 s | 1.1180 s | GNU `__typeof__` |
| echo_pack | 0.4202 s | 0.9151 s | GNU `__typeof__` |
| ledger_bin | 0.8439 s | 0.7194 s | GNU `__typeof__` |
| rail_transfer | 0.9718 s | 0.0693 s | GNU `__typeof__` |
| scar_life | 0.5267 s | 25.4418 s | GNU `__typeof__` |
| tally_lang | 0.9835 s | 1.1717 s | GNU `__typeof__` |
| term_rank | 1.1320 s | 1.8676 s | GNU `__typeof__` |
| ticket_audit | 2.4331 s | 2.5368 s | GNU `__typeof__` |
| tree_fold | 1.3090 s | 1.2964 s | GNU `__typeof__` |

**40 corpus programs**, the same list and order as tccprobe1:
`g01_010 g02_002 g18_038 g25_038 g05_016 g00_004 g03_018 g04_016 g17_002 g04_004 g06_000 g04_038
g17_026 g13_014 g18_006 g19_018 g09_026 g22_022 g13_038 g04_008 g16_004 g00_000 g21_032 g20_000
g09_002 g22_014 g12_038 g09_032 g06_004 g04_034 g03_012 g21_020 g23_028 g03_006 g12_008 g18_016
g23_032 g02_000 g13_018 g25_000`.
The 5 candidates AIL refused are the same five as tccprobe1 (`g20_020`, `g14_012`, `g15_024`,
`g22_034`, `g15_028`).

Emitted C per program: 48 single-unit, 2 multi-unit (`g02_002`, `g13_038`). Median gcc `-O2`
build 0.9777 s (range 0.131–17.2 s).

## The price (Amdahl, from `CTIME_2026-11.md`)

The gcc phase is **26.0%** of pooled cold wall, so its Amdahl bound on the whole build is
`1/(1−0.26) = 1.351×`.

- **Achieved compile ratio** `gcc_time / c2m_time`: **undefined** — c2m builds 0 of 50, so there is no
  c2m compile time. Achieved whole-build speedup: **1.00× (0% of the 1.351× bound)**.
- For reference, **if** c2m compiled AIL's C at MIR's README claim (about 80× gcc `-O2`):
  `1/(0.74 + 0.26/80) = 1.345×`, i.e. **99.6% of the bound**. The bound is captured quickly: a
  compiler only 2× faster than gcc gives `1/(0.74+0.26/2) = 1.149×` (85.0% of the bound), 10× gives
  1.306× (96.6%). So speed is not the constraint — compatibility is: today's ratio is 0×.
- The measured c2m cost is the time to the first error, median **91 ms** (vs gcc's 0.978 s to a full
  build). That is c2m parsing 0.15–2.4 MB of generated C to the first incompatible construct, not a
  compile, and it cannot be turned into a build ratio.

## Recommendation for devcc2

**Neither tcc nor c2m can build AIL's C today (0/50 both). Do not add a `--cc=mir` mode yet.**

If one fast dev compiler is added, **prefer tcc**, and treat mir as a later option:
- tcc produces an ELF executable, so `ail compile -o` maps directly; c2m **cannot produce an
  executable at all** — only `-eg`/`mir-bin-run` — so it could only back a `run`-style command, never
  `compile -o`. (The owner decision allows `--cc=tcc|mir` only if the output is byte-identical; a
  run-only mode cannot satisfy that contract on the compile path.)
- tcc's blockers are 4 generated-C constructs with local fixes, and `lab/tccdev` already has 511-case
  evidence; c2m's blockers are in the runtime preamble and include `__typeof__`, which c2m does not
  implement at all.

Refusal lists the mode must implement:
- **tcc mode** must refuse a program whose generated C contains: `_Thread_local` (tcc has no TLS),
  an unsized struct-array compound literal from runtime values, an unsized struct-array declaration
  from runtime values, `__builtin_unreachable` (and any `__builtin_*` tcc lacks), `__int128` /
  `__uint128_t`, and inline asm. (tccprobe1's buckets, 0/50 today.)
- **mir/c2m mode** must refuse: GNU `__typeof__` (the `ail_len_t` typedef),
  `__int128`, `__uint128_t`, unsized struct-array compound literals, and unresolved builtins/asm —
  i.e. all 50 today. It can only `run`, not produce an executable.

The two cheapest unblockers for mir, if it is pursued: (1) replace
`typedef __typeof__(_Generic(...)) ail_len_t;` (`cruntime.py:199-200`) with a plain
`#if __SIZEOF_LONG__ == 8` `typedef long long ail_len_t;` — unblocks 32/50; (2) remove the 128-bit
range-slice and shift arithmetic (`cruntime.py:16893`, `3841-3844`) — the other 18. Even then c2m
still rejects the unsized compound literal on the print path and cannot write an executable, so tcc
remains the better target.

## Probes run

No compiler or runtime behaviour was changed, so there is no AIL-vs-CPython probe and
`bash ~/tools/cmp.sh` does not apply. The probes below check the measurement and every claim this
report makes about c2m.

| probe | what it checks | result |
| --- | --- | --- |
| `/tmp/probes/c2m_limits.py` (17 checks) | all four run modes exist and agree; `-o` alone and `-c` write binary MIR (`MIR\xe2`), not ELF; `_Generic` alone is accepted but GNU `typeof`/`__typeof__` is not implemented (even `__typeof__(x)` fails); `__int128` is rejected; `_Thread_local` and `__attribute__((always_inline))` and `_Pragma` are accepted; `__asm__` / `__builtin_unreachable` fail as unresolved imports; unsized compound literal from runtime values is rejected while the unsized declaration is accepted; `-lm` is rejected but `sqrt` resolves from `libm.so.6` | 17/17 |
| `PIPE_CC` logging shim | the exact argv `$PIPE_CC` receives (all gcc-only flags) and the CLI exit for tcc and c2m | argv as quoted above; both exit 3, no artifact |
| `c2m -O2 -o OUT prog.c` on a valid C file | a c2m "success" is binary MIR, not an executable | exit 0, magic `MIR\xe2` |
| corpus-selection replay | the 45 candidates tried and the 5 refusals match tccprobe1 | identical list and refusals |
| gcc determinism | 50/50 gcc `-O2` output sets identical across 3 runs | 50/50 |

Required modules on this tree:
`python3 -B -m unittest test_ail_safetynet test_ail_files test_ail_corpus_findings3` →
**25 tests, OK (skipped=1)**. Under `ulimit -v 1500000` one general-path case (`S4_generators_gc`)
stopped after its first line; the same case builds and matches CPython exactly (stdout and exit 0)
without the cap, so that is the memory cap, not a regression.

## Appendix: devcc2 report (previously the content of this file)

Preserved verbatim; it was written by devcc2 from `lab/tccdev`, not by this job.

# devcc2: opt-in `--cc=tcc|mir`

Date: 2026-11-05. Base: `staging:integ` at `5b8f1bb` (the job exported no `lab/devcc/RESULTS.md` from devcc1 and
no `origin/integ` ref, so this work uses the compiler and measurements devcc1's predecessor left in
`lab/tccdev/results.json`, `lab/tccdev/measure.py` and `docs/design/TCC_DEV.md`).

## What the mode is

* Default/release builds are unchanged: with neither `--cc` nor `AIL_DEVCC`, `pyc._cc` never imports
  `devcc.py`, and the gcc command line is byte-for-byte the one it was before.
* `--cc=tcc` maps the C step to `tcc` on PATH.  gcc-only flags (`-O2`, `-fno-tree-slp-vectorize`,
  `-ffp-contract=off`, `-fopenmp-simd`, `-Werror=*`, `-fno-asynchronous-unwind-tables`,
  `-Wl,--gc-sections`, `-ffunction-sections`, `-fdata-sections`) are dropped; `-I/-D/-U/-L/-l/-o/-c`,
  input objects and `-pthread` are kept.  The three checked-overflow builtins get the portable
  definitions already measured in `lab/tccdev/tcc_prelude.h`.
* `--cc=mir` maps to `$AIL_MIR_C2M`, else `c2m` on PATH.  c2m cannot write an executable, so
  `compile -o` refuses it by name; the mapping exists only for a run-style command.
* Every generated C source is scanned before the tool runs.  A construct the tool does not build
  identically to gcc refuses the whole program with
  `--cc=<x>: this program uses <construct> (line N of the generated C), which <x> does not build
  identically to gcc; build without --cc`.

Compiler named by the devcc1 evidence: `tcc version 0.9.28rc 2026-10-16 mob@e23dabe` (x86_64 Linux).
Its refused bucket is `__int128`; the checked-overflow builtins are the only builtins it lacks and are
covered by the prelude.  Attributes, `__typeof__`, `__builtin_expect`, `__builtin_unreachable`,
`__builtin_constant_p`, `__builtin_memcpy` and statement expressions are accepted/ignored by tcc.

## No-flag check (done)

120 inputs: the 10 `lab/compare/src/*/typed.py`, the 10 `lab/compare/src/*/main.py`, and the first 100
sorted `lab/corpus/programs/*/*.py` (sorted paths).  Each was built with the base (`work` = `5b8f1bb`)
and with this change in a fresh directory, `AIL_NO_CACHE=1`, `AIL_SERVER=0`, `PYTHONHASHSEED=0`,
`--debug-dir`.

| inputs | C hash and executable hash identical | built | refused at compile time |
|---:|---:|---:|---:|
| 120 | 120 | 115 | 5 |

Zero differences.  The 5 refusals are identical on both sides (corpus programs the compiler already
refused), not caused by this change.

## Opt-in corpus gate

`tcc` is not installed on this runner, so no real tcc compile was possible here.  To exercise the
mapping, prelude and refusal scan end to end, a stand-in `tcc` that `exec gcc "$@"` was placed first on
PATH.  That proves the rewrite path but not tcc's own code generation; the tcc correctness evidence is
the 511 public+hidden cases in `lab/tccdev/results.json` (zero failures, stdout and exit status identical
to gcc).

On the 10 `lab/compare/src/*/main.ail` (the files `lab/tccdev/measure.py` builds) plus the first 50
sorted corpus programs:

| programs | built with the mode | refused by name | built and differing |
|---:|---:|---:|---:|
| 60 | 46 | 14 (`__int128`) | 0 |

All 10 compare tasks built; the 14 refusals are generated-C `__int128` (range slice / `list(range(...))` /
3-argument `pow`), refused before the C compiler ran.

## Compile time

Not measured for tcc on this runner (tool absent), so no whole-build projection is written.  The
devcc1 evidence is: `tcc -c` 5-12 ms and link 2-4 ms against `gcc -c` 0.35-1.34 s on the ten tasks;
the whole cold build falls 24.48 s -> 19.56 s over the ten medians (2.03 s -> 1.64 s median task,
1.2-1.9x), with the Python front end left untouched.  The C stage alone is 5-12 ms.

## Tests

`AIL_CURRENT/test_ail_devcc.py`: unit tests for mode selection, `mir` refusal, gcc-only flag removal,
prelude injection, `__int128` refusal wording, and the default gcc `-O2` command line;
build tests for five programs against gcc, one named refusal, and default gcc `-O2` skip when `tcc` is
not installed.  Registered as `AIL_CURRENT/tests.d/test_ail_devcc.txt`.
