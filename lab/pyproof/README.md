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
modified.

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

1. builds with `--strict` and keeps the refusal text if it fails;
2. builds with the default command and classifies the build as `typed`
   (no fallback note), `general` (`note: ... built on the general path ...`)
   or `refused` (non-zero exit);
3. runs the default binary and `python3` on the same input, comparing stdout
   and the exit status; `wrong` means the build succeeded but the run does not
   match CPython;
4. times both, median of three (CPython runs time out at 2 s);
5. writes `results.jsonl` and `RESULTS.md`.

Builds run two at a time, with `AIL_NO_CACHE=1`, a 120 s timeout and a 1.5 GB
address-space cap.  A refusal bucket is a refusal text with names, numbers and
paths replaced by placeholders; **alone** counts programs whose only reason is
that bucket, **listed** counts programs that mention it.  Build timeouts are
reported in the program table but are not refusal-text buckets.

## Current result

From the run recorded in `results.jsonl` (base `0aa7d3c07be231f62cb221c62e4d36e2e8392ea8`,
the branch head; this checkout has no `origin/integ` ref, so that is the
recorded base), CPython 3.12.3:

**typed 24 / 55, general 15, refused 16, wrong 0**; geomean speed-up over
CPython of the programs that build: **6.32x**.

Ranked blockers (alone / listed), each with a reproducer in `repro/`:

| alone | listed | bucket |
|---:|---:|---|
| 6 | 6 | `import of 'X' is not available` |
| 3 | 3 | `a list parameter is read-only` |
| 3 | 3 | `an integer literal or constant expression overflows int64` |
| 2 | 2 | `a dict of containers (lists, sets or dicts as values)` |
| 2 | 2 | `the constant None` |

The 6 import refusals are the three Rust-crate examples and their benches
(`rle`, `fnvhash`, `textstat`), whose generated `*_ffi` module is not checked
in.  The read-only list bucket is `nqueens`, `scimark_fft` and
`spectral_norm`; the int64 bucket is `examples/hybrid/fallback_demo.py` plus
the `chain_relax` and `rail_transfer` compare programs; `ledger_bin` and the
`run.py` runner are the dict-of-containers cases; `richards` and `csv_rollup`
are the constant-None cases.  `tally_lang` (field list/dict) has a fifth
reproducer.  A general-path fallback is a blocker too: it is the reason the
default build leaves the typed path, and `RESULTS.md` counts it alongside the
strict refusals.

Two programs, `lab/compare/src/scar_life/main.py` and
`lab/compare/src/ticket_audit/main.py`, hit the 120 s build timeout on both the
strict and default builds (240 s total each; re-running `ticket_audit` alone
with one job reproduced it), so they are counted as refused with the timeout
text and are outside the refusal-text buckets.  No program produced a `wrong`
result.

## Verification

The three top-bucket reproducers and the two extra ones were each built in
both modes and run with `bash ~/tools/cmp.sh`, and separately through
`report.py` on a fixture list.  All behave as the bucket says:

| reproducer | strict build | default build |
|---|---|---|
| `import-of-x-is-not-available.py` | refused: `import of 'rle_ffi' is not available` | refused, same text |
| `a-list-parameter-is-read-only.py` | refused: `'xs' is a list parameter, which is read-only` | general: `note: ... because 'xs' is a list parameter, which is read-only` |
| `an-integer-literal-or-constant-expression-overflows-int64.py` | refused: `int64 ... out of range` | refused, same text |
| `a-dict-of-containers-lists-sets-or-dicts-as-values.py` | refused: `uses ... as a dict of containers` | general, same reason |
| `a-field-list-or-dict-gets-bools-and-numbers.py` | refused: `field ... is a list or dict that gets bools and numbers` | general, same reason |

No program's source was changed to make it build.  `results.jsonl` has the
same fields as `lab/stdcensus` (`name`, `path`, `input`, `result`,
`strict_path`, `strict_reason`, `first_reason`, `reasons`, `build_seconds`,
exit codes, stdout comparison, CPython/AIL timings and `speedup`).

## Files

* `programs.txt` - the fixed list and input specs.
* `report.py` - the runner and renderer.
* `results.jsonl` - one record per program, in list order.
* `RESULTS.md` - generated counts, program table, buckets and reproducers.
* `repro/` - small programs, one per bucket, verified to produce the same
  normalised refusal or fallback.
