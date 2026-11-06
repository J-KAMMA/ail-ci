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

## devcc3 price, written before any edit

The speed-claims rule needs the phase share, the Amdahl bound and a projection before the work starts.

* Share: gcc code generation plus link is 26.0% of pooled cold wall in `lab/profile/CTIME_2026-11.md`
  (the gcc codegen column; gcc read and link are separate).  The bound is `1 / (1 - 0.260) = 1.35x`.
* Projection from the devcc1 measurement (`docs/design/TCC_DEV.md`, tcc mob `e23dabe`): the sum of the
  ten task medians falls from 24.48 s to 19.56 s, 1.25x, while the front end is untouched.
* Halved, because this repo's compile-time estimates have overshot 2-3x: **1.12x** on development
  builds.  Release and default builds are unchanged; tcc run time is 1.7-8.2x slower, acceptable only
  for an edit loop.
* The gate below measures the 1.25x again with `--cc=tcc`; the halved 1.12x is the number to hold.

## devcc3: the gate against a real tcc

Measured 2026-11-06 on the 4-core GitHub Actions runner, base `origin/integ`.

Two real compilers, both outside the repository:

| tool | source | `tcc -v` |
| --- | --- | --- |
| Ubuntu package | `sudo apt-get install -y tcc` (`0.9.27+git20200814.62c30a4a-1`) | `tcc version 0.9.27 (x86_64 Linux)` |
| mob | `git clone https://github.com/TinyCC/tinycc` at `e23dabe`, `./configure --prefix=$HOME/scratch/tcc-mob-install && make -j 2 && make install` | `tcc version 0.9.28rc 2026-10-16 HEAD@e23dabed (x86_64 Linux)` |

`gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`, python 3.12.3.  Sub-step 1's three tasks
(`berth_sim`, `chain_relax`, `tree_fold`, `--cc=tcc`):

| task | tcc 0.9.27 | tcc 0.9.28rc |
| --- | --- | --- |
| berth_sim | refused, `index too large` (unsized aggregate) | built, ran |
| chain_relax | refused, `undefined symbol '__builtin_unreachable'` | built, ran |
| tree_fold | refused, `index too large` | built, ran |

Those 0.9.27 messages come from running the generated C through that tcc directly (the version
check refuses earlier, which is the stance below).

### Stance: refuse tcc 0.9.27 by its `tcc -v`

`devcc.py` refuses any tcc older than 0.9.28 before scanning or compiling:

```
--cc=tcc: tcc 0.9.27 cannot build this generated C; use tcc 0.9.28 or later, or build without --cc
```

The version was chosen over adding 0.9.27's constructs to the scan because nearly every program
would be refused anyway: tccprobe1 measured 0 of 50 programs building (`_Thread_local` 19, unsized
aggregate literals/declarations 23, `__builtin_unreachable` 7, `__int128` 1), and the three tasks
above failed on three different constructs.  The whole gate confirms it: 0 of 159 build.  The check
runs before the construct scan, so 0.9.27 always gets this one named message.

### The missing constructs the gate found on 0.9.28

The first gate run (before the scan was extended) had 5 build failures under 0.9.28, all outside
devcc2's scan:

| construct | programs | tcc's message |
| --- | ---: | --- |
| `__uint128_t` (the `__int128` regex only matched `__int128`) | 3 | `cannot convert 'unsigned long' to 'struct __uint128__'` |
| `__builtin_fabs` | 1 | `unresolved reference to '__builtin_fabs'` |
| `__builtin_isinf` | 1 | `unresolved reference to '__builtin_isinf'` |

All three were added to `_TCC_CONSTRUCTS`; `__int128` now also matches `__int128_t` and
`__uint128_t`.  After the change those five are named refusals, and the gate has 0 failed builds.

### The gate

`python3 lab/devcc/gate.py --tcc /usr/bin/tcc --tcc ~/scratch/tcc-mob-install/bin/tcc --jobs 2`
builds and runs 160 cases: the 10 `lab/compare/src/*/main.ail` (twice, as in the task), tccprobe1's
40 seeded `corpus/gdev` programs, and the first 100 sorted `lab/corpus/programs/*/*.py`.  One corpus
program does not compile with gcc either, so 159 are counted.  stdout, stderr and exit status are
compared byte for byte against the gcc `-O2` build; the C step is the median of 3.

| tcc | cases | gcc -O2 built | tcc built | identical | refused | differing | failed | timeout | C step gcc (s) | C step tcc (s) | gcc/tcc |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.9.27 | 159 | 159 | 0 | 0 | 159 | **0** | 0 | 0 | 0.9669 | n/a | n/a |
| 0.9.28rc | 159 | 159 | 96 | 96 | 63 | **0** | 0 | 0 | 0.9669 | 0.0182 | 49.9x |

Refusals on 0.9.28: 61 `__int128`, 1 `__builtin_fabs`, 1 `__builtin_isinf` (all named, before the C
compiler runs).  On 0.9.27: 159 version refusals.  **Zero programs build and differ, on either
version, so the second number the task moves is 0.**  The identical count is 96 as measured.

### Compile ratio and projection

C step, medians: gcc `-O2` 0.9669 s against tcc 0.0182 s; summed over the 96 pairs, **49.9x**; over
the 10 compare tasks, **83.7x**.  The first, less loaded run of the same gate measured 0.6764 s and
73.4x (97.5x on the compare tasks), so the ratio is load-sensitive but two orders of magnitude.

Against the price written before the work (gcc C stage 26.0% of pooled cold wall, Amdahl bound
`1/(1-0.260) = 1.35x`): shrinking that 26% by 49.9x projects `1/(0.740 + 0.260/49.9) = 1.346x`,
i.e. at the bound.  Halved by the speed-claims rule the projection is **1.17x**; the number written
into the price before any edit was **1.12x** (the devcc1 measurement, 24.48 s -> 19.56 s, 1.25x
halved).  Both sit inside the 1.35x bound; the conservative 1.12x stays the number to hold for
development builds.  Release and default builds are untouched, and tcc run time remains 1.7-8.2x
slower, which is acceptable only for an edit loop.

### No-flag check on devcc2's 120 inputs

Builds each of the 10 `lab/compare/src/*/typed.py`, the 10 `lab/compare/src/*/main.py` and the first
100 sorted `lab/corpus/programs/*/*.py` with the base tree (`git archive HEAD`) and with this change,
in fresh directories with `AIL_NO_CACHE=1`, `AIL_SERVER=0`, `PYTHONHASHSEED=0` and `--debug-dir`,
and compares `sha256(program.c)`, `sha256(executable)` and the refusal text.

| inputs | C hash and executable hash identical | built | refused at compile time |
|---:|---:|---:|---:|
| 120 | 120 | 115 | 5 |

Zero differences (`differ: 0`).  The 5 refusals are identical on both sides: the compiler refuses
those corpus programs before any C compiler runs, with the same text.

### Tests and probes

`AIL_CURRENT/test_ail_devcc.py` has 13 tests.  With tcc 0.9.27 on PATH the two 0.9.28-only build
tests skip and the new `test_real_tcc_is_supported_or_refused_by_version` asserts the exact version
refusal.  With the mob build on PATH all 13 pass in 9.4 s, including five programs that build and run
identically under `--cc=tcc` and the `__int128` refusal.  New unit tests cover the version refusal
(`0.9.27`, and `0.9.28rc ...` parsed as 0.9.28) and the `__uint128_t` / `__int128_t` /
`__builtin_fabs` / `__builtin_isinf` scan entries without needing a real tcc.

Probes in `/tmp/probes`, each run through the default build, `AIL_UNIFIED_FORCE=1` (`tools/cmp.sh`)
and `--cc=tcc`:

| probe | default / unified | `--cc=tcc` (0.9.28rc) |
| --- | --- | --- |
| p_arith: int arithmetic, int64 edges, values from a list, dict and attribute | matches CPython | refused `__int128` |
| p_types: reals in a class attribute, dict value, list item | matches CPython | refused `__int128` |
| p_float: float sum, `int()`, `round()` | matches CPython | refused `__builtin_isinf` |
| p_text: join, replace, f-string | matches CPython | identical to the default build |
| p_fabs: `abs()` of a runtime float | matches CPython | refused `__builtin_fabs` |
| p_isinf: `int()` of a float outside int64 | refused by name by the compiler | never reaches the C step |
| p_u128: runtime `int / int` true division | matches CPython | refused `__int128` |
| p_oldversion: trivial program | matches CPython | 0.9.27: exact version refusal; 0.9.28rc: identical |

Required modules on the final commit: `test_ail_files` OK (18 tests, 1 skip), `test_ail_corpus_findings3`
OK (2 tests), `test_ail_safetynet` 1 failure, `S4_generators_gc` (prints only its first line).  The
same test fails identically against the base tree (`git archive HEAD`), so it is pre-existing on this
runner and unrelated to this change.  The 20 CI shards were not run: this runner's rules forbid
pushing, so the branch is committed locally and not opened as a PR.
