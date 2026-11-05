# pyproof: typed reach of the repository's plain-Python programs

`lab/pyproof` answers one question with a fixed, reproducible list: of every
ordinary Python program already in this repository, how many does the default
AIL build take on the typed path, how many fall back to the general path, how
many are refused, and which refusal blocks the most programs?

This is the program-level counterpart of `lab/stdcensus` (stdlib imports).  It
does not edit any compiler file and does not change any program to make it
build.

## The list

`programs.txt` has **54** programs in a fixed order.  It covers:

| source | programs |
|---|---:|
| `AIL_CURRENT/language_examples/quickstart/` | 3 |
| `examples/` (crate, ffi, hybrid, mdlite, tutorial_project) | 29 |
| `lab/pyperf/bench/` | 10 |
| `lab/compare/src/*/main.py` | 10 |
| `lab/compare_cand/src/*/main.py` | 2 |

A file is included when it is a `.py` program with a `__main__` path or a
top-level call that prints.  Excluded are `typed.py` sources (the annotated AIL
programs in the compare labs), test modules, generated FFI helper modules with
no entry point (`math_gen_ffi.py`, `zlib_gen_ffi.py`), `examples/crate/*/bigbuffer.py`
(a helper module), and `.ail` files.  The programs are never modified.

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

From the run recorded in `results.jsonl` (base integ
`803122d3cd9f139fd84e3cfc52bd9dad110cf2cb`, CPython 3.12.3):

**typed 24 / 54, general 16, refused 14, wrong 0**; geomean speed-up over
CPython of the programs that build: **6.19x**.

Ranked blockers (alone / listed), each with a reproducer in `repro/`:

| alone | listed | bucket |
|---:|---:|---|
| 6 | 6 | `import of 'X' is not available` |
| 3 | 3 | `an integer literal or constant expression overflows int64` |
| 1 | 1 | `a field list or dict gets bools and numbers` |

The 6 import refusals are the three Rust-crate examples and their benches
(`rle`, `fnvhash`, `textstat`), whose generated `*_ffi` module is not checked
in.  The int64 bucket is `examples/hybrid/fallback_demo.py` plus the
`chain_relax` and `rail_transfer` compare programs, all of which deliberately
use values above `2**63`.  The `tally_lang` compare program is the field
list/dict case.

One program, `lab/compare/src/scar_life/main.py`, hit the 120 s build timeout
on both the strict and default builds (240 s total), so it is counted as
refused with the timeout text and is outside the refusal-text buckets.  No
program produced a `wrong` result.

## Files

* `programs.txt` - the fixed list and input specs.
* `report.py` - the runner and renderer.
* `results.jsonl` - one record per program, in list order.
* `RESULTS.md` - generated counts, program table, buckets and reproducers.
* `repro/` - one small program per top bucket, verified to produce the same
  normalised refusal with `--strict`.
