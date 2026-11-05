# pyproof: typed reach of the repository's plain-Python programs

`lab/pyproof` answers one question with a fixed, reproducible list: of every
ordinary Python program already in this repository, how many does the default
AIL build take on the typed path, how many fall back to the general path, how
many are refused, and which refusal blocks the most programs?

This is the program-level counterpart of `lab/stdcensus` (stdlib imports).  It
does not edit any compiler file and does not change any program to make it
build.

## The list

`programs.txt` has **55** programs in a fixed order.  It covers:

| source | programs |
|---|---:|
| `AIL_CURRENT/language_examples/quickstart/` | 3 |
| `examples/` (crate, ffi, hybrid, mdlite, tutorial_project) | 29 |
| `lab/pyperf/bench/` | 10 |
| `lab/pyperf/run.py` (the lab's own runner, `--help`) | 1 |
| `lab/compare/src/*/main.py` | 10 |
| `lab/compare_cand/src/*/main.py` | 2 |

A file is included when it is a `.py` program with a `__main__` path or a
top-level call that prints.  Excluded are `typed.py` sources (the annotated AIL
programs in the compare labs), test modules, generated FFI helper modules with
no entry point (`math_gen_ffi.py`, `zlib_gen_ffi.py`), `examples/crate/*/bigbuffer.py`
(a helper module), the remaining `lab/pyperf/*.py` modules (they are import-only
helpers with no entry point), and `.ail` files.  The programs are never
modified.  The six `examples/crate/` rows are ordinary Python only after
`ail_cargo.py build` writes their `*_ffi.py` stub and static library; the
runner does that with the same options as `test_ail_examples_crate.py`.

Each line is `path<TAB>input`.  Input comes from the lab that owns the program:

* `none` for the self-contained examples and the FFI/crate `main.py` files;
* `stdin:FILE` for the tutorial steps (`sample.log`) and `mdlite` (a Markdown
  file from the tutorial);
* `argv:...` for the pyperf kernels at `lab/pyperf/run.py`'s `SMALL` sizes, the
  hybrid examples at reduced sizes, `gen_log.py SEED N`, and the crate benches
  (a small file in the work directory);
* `gen:DIR` for the compare-lab tasks: `report.py` calls the task's
  `gen.py:cases(rng)` with the same seed the lab uses and takes the first
  public case.  This keeps every compare program's input tiny.

The small inputs are deliberate: each CPython run is capped at 2 s.  The list
stays complete even where an input was cut down.  `examples/mdlite/make_big.py`
is run with 1 MB rather than its default 20 MB, and the compare tasks use a
public case rather than the 32 MB+ performance input.

## The runner

```sh
python3 lab/pyproof/report.py                 # full census (~12 min here)
python3 lab/pyproof/report.py -j 2 --only examples/hybrid/collatz.py
python3 lab/pyproof/report.py --render-only   # rebuild RESULTS.md from results.jsonl
```

For each program `report.py`:

1. builds the Rust crate first when the program is under `examples/crate/`
   (`ail_cargo.py build` with the same header and `--check` that
   `test_ail_examples_crate.py` uses), then copies its generated `*_ffi.py`
   and static library into the work directory;
2. runs `python3` on the same input **before** classifying the build, so a
   missing generated artifact or a bad input cannot masquerade as a language
   refusal; a quick non-zero CPython exit makes the row `not run`, not
   `refused` (a CPython timeout is not a failure, because the compiler
   refusal stands on its own);
3. builds with `--strict` and keeps the refusal text if it fails;
4. builds with the default command and classifies the build as `typed`
   (no fallback note), `general` (`note: ... built on the general path ...`)
   or `refused` (non-zero exit);
5. runs the default binary on the same input, comparing stdout and the exit
   status with CPython; `wrong` means the build succeeded but the run does not
   match;
6. times both, median of three (CPython runs time out at 2 s);
7. writes `results.jsonl` and `RESULTS.md`.

Non-crate programs are compiled from the copies in the work directory but the
CPython oracle runs the real repository path, so `__file__`-relative lookups
(for example `examples/ffi/bindgen/measure.py`) still find the repository.

Builds run two at a time, with `AIL_NO_CACHE=1`, a 120 s timeout and a 1.5 GB
address-space cap.  A refusal bucket is a refusal text with names, numbers and
paths replaced by placeholders; **alone** counts programs whose only reason is
that bucket, **listed** counts programs that mention it.  Build timeouts are
reported in the program table but are not refusal-text buckets.

`integ_sha()` never falls back to `HEAD` while calling it `integ`: the report
records the base ref that actually resolved (`origin/integ`, `integ`, or the
`work` branch) next to its sha.

## Current result

From the run recorded in `results.jsonl` (base `work`
`88e666c02746712df674f02d4ce83de1a9fae3df`; this checkout has no
`origin/integ` or `integ` ref, so the base is named `work`, not `integ`),
CPython 3.12.3:

**typed 29 / 55, general 16, refused 8, wrong 2**; geomean speed-up over
CPython of the programs that build: **6.59x**.

Ranked blockers (alone / listed), each with a reproducer in `repro/`:

| alone | listed | bucket |
|---:|---:|---|
| 3 | 3 | `a dict of containers (lists, sets or dicts as values)` |
| 3 | 3 | `a list parameter is read-only` |
| 3 | 3 | `an integer literal or constant expression overflows int64` |
| 2 | 2 | `the constant None` |
| 1 | 1 | `a field list or dict gets bools and numbers` |

The Rust-crate rows are now built with `ail_cargo.py build`, so five of the
six are typed and match CPython: `rle/main.py`, `rle/bench.py`,
`fnvhash/bench.py`, `textstat/main.py` and `textstat/bench.py`.  The sixth,
`examples/crate/fnvhash/main.py`, builds typed but the default binary stops
with `OverflowError: integer overflow in +` while CPython prints exact u64
values, so it is a `wrong` row (the crate's own test passes `--exact-int`).

The read-only list bucket is `nqueens`, `scimark_fft` and
`spectral_norm`; the int64 bucket is `examples/hybrid/fallback_demo.py` plus
the `chain_relax` and `rail_transfer` compare programs; the dict-of-containers
bucket is `run.py`, `ledger_bin` and `ticket_audit`; `richards` and
`csv_rollup` are the constant-None cases.  `tally_lang` (field list/dict) has
an extra reproducer.  A general-path fallback is a blocker too: it is the
reason the default build leaves the typed path, and `RESULTS.md` counts it
alongside the strict refusals.

The strict build of `scar_life` and `term_rank`, and both builds of
`ticket_audit`, exceed the 120 s timeout.  `scar_life` and `ticket_audit` still
produce a default binary: `ticket_audit` matches CPython on the general path,
while `scar_life` is `wrong` (default build general, run stops with
`OverflowError: integer overflow in int()`).  `term_rank` also matches on the
general path.

`examples/ffi/bindgen/measure.py` is `refused` by the compiler for
`library() returns a path without saying so`; CPython runs it for 1.0 s, so the
refusal is not an artifact failure.

## Verification

The five bucket reproducers and the two `wrong` reproducers were each built
with `--strict` and with the default command, and the default/general binaries
were run through `bash ~/tools/cmp.sh`.  All behave as their row says:

| reproducer | strict build | default build |
|---|---|---|
| `import-of-x-is-not-available.py` | refused: `import of 'rle_ffi' is not available` | refused, same text (CPython also stops: no crate is built here) |
| `a-list-parameter-is-read-only.py` | refused: `'xs' is a list parameter, which is read-only` | general: same reason, stdout matches |
| `an-integer-literal-or-constant-expression-overflows-int64.py` | refused: `int64 constant expression out of range` | refused, same text |
| `a-dict-of-containers-lists-sets-or-dicts-as-values.py` | refused: `uses ... as a dict of containers` | general, same reason, stdout matches |
| `a-field-list-or-dict-gets-bools-and-numbers.py` | refused: `field ... is a list or dict that gets bools and numbers` | general, same reason |
| `wrong-integer-overflow-at-runtime.py` | typed | typed binary exits 1 with `OverflowError: integer overflow in +`; CPython prints the exact value |
| `wrong-integer-overflow-in-int.py` | typed | typed binary exits 1 with `OverflowError: integer overflow in int()`; CPython prints the exact value |

No program's source was changed to make it build.  `results.jsonl` has the
same fields as `lab/stdcensus` (`name`, `path`, `input`, `result`,
`strict_path`, `strict_reason`, `first_reason`, `reasons`, `build_seconds`,
exit codes, stdout comparison, CPython/AIL timings and `speedup`), plus
`base_ref` for the provenance line.

## Files

* `programs.txt` - the fixed list and input specs.
* `report.py` - the runner and renderer.
* `results.jsonl` - one record per program, in list order.
* `RESULTS.md` - generated counts, program table, buckets and reproducers.
* `repro/` - small programs, one per bucket plus the two `wrong` rows,
  verified to produce the same refusal, fallback or runtime overflow.
