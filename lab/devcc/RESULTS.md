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
