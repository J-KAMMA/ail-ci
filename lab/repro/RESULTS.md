# Reproducible builds, measured

Measured 2026-11-06 on `origin/integ` (branch `job-ffrepro1-11061145`) with
`tools/repro_check.py`. Measure-only: no compiler file was edited, so no instruction count moved.

Question: does one source give one byte-identical executable when it is built in a short path and
in a long path, with a different `TMPDIR`, its own `HOME`, a different `PYTHONHASHSEED` and two
different `SOURCE_DATE_EPOCH` values?

## Method

Corpus = the 10 `lab/compare/src/*/main.py` programs, every `lab/stdlib/*/*.py` program and every
`examples/**/*.py` program: **467 programs** (10 compare, 390 stdlib, 67 examples).

Each program is built twice:

| | setup A | setup B |
|---|---|---|
| working directory | `/tmp/a/x/<slug>` | `/tmp/b/longer/path/x/<slug>` |
| `TMPDIR` | `/tmp/a/tmp` | `/tmp/b/tmp` |
| `HOME` | `/tmp/a/home` | `/tmp/b/home` |
| `SOURCE_DATE_EPOCH` | `1000000000` | `2000000000` |
| `PYTHONHASHSEED` | `0` | `1` |

The rest of the environment is only `PATH`, `LANG`, `LC_ALL`, `PYTHONUTF8=1`,
`PYTHONDONTWRITEBYTECODE=1` and `AIL_NO_CACHE=1`; nothing is inherited from the caller. The source
is copied into each working directory under its own name, so the file *name* is the same and only
the directory differs. Both builds pass `--debug-dir`, so `program.c` is compared as well as the
executable; both are compared by sha256. Every built executable is run once under both builds and
the stdout and exit status must agree. Builds run under a 1.5 GB address-space limit, at most two
at a time.

On a difference the tool prints the first differing line of `program.c` (with the two lines) and,
when only the executable differs, the first differing ELF section and byte offset; it sorts a C
difference into `hash order`, `absolute path`, `temporary name`, `time`, `counter` or `other`.

## Headline numbers

The clock stopped the run after 100 of the 467 programs (36 minutes at two builds at a time on a
shared runner; `compare/scar_life` alone is a 4-minute build). The 100 measured programs are all 10
compare programs and 90 stdlib programs in 8 modules. The 367 unmeasured programs are the subject of
the follow-up in the last section; this document does not claim a result for them.

| measure | count |
|---------|-------|
| programs measured | **100** |
| identical in both setups (`program.c` **and** executable sha256) | **82** |
| different in either | **0** |
| not built in at least one setup | **18** |
| programs whose two builds printed different stdout or exited differently | **0** |
| remaining unmeasured | 367 |

By family:

| family | measured | identical | not built | different |
|--------|---------:|----------:|----------:|----------:|
| compare | 10 | 6 | 4 | 0 |
| stdlib (array, base64, bisect, collections, colorsys, csv, datetime, decimal) | 90 | 76 | 14 | 0 |
| examples | 0 | 0 | 0 | 0 |

Module by module (identical measured / module size): `array` 9/12, `base64` 10/12, `bisect` 12/12,
`collections` 9/12, `colorsys` 13/13, `csv` 9/12, `datetime` 9/12, `decimal` 5/12.

## Difference classes

Every class `tools/repro_check.py` can name has count **0**. No difference was observed, so there is
no example diff to show. The `file that would emit it` column is the hook to use on the first
occurrence; the C is emitted by `AIL_CURRENT/python/pkg-v12/cruntime.py` (the tree has no
`AIL_CURRENT/ir/emit_c.py`), so the named files are the ones in this tree that build names and
paths:

| class | count | file that would emit it | hook that would remove it |
|-------|------:|-------------------------|---------------------------|
| hash order | 0 | `python/pkg-v12/pyfunc.py` (sets around lines 7, 92, 221, 504, 2109) | sort the set before iterating (line 415 already sorts `kinds`) |
| absolute path | 0 | `python/pkg-v12/c_object.py:125,145` (`.resolve()` of source/output), `buildcache.py:243` | keep the source path out of the C; otherwise add `-ffile-prefix-map=<dir>=.` where the cc command is assembled (`python/pkg-v12/cruntime.py`, the `compile_link` command list) |
| temporary name | 0 | `c_api.py:253`, `c_export.py:226`, `c_object.py:356`, `c_api_bridge.py:165` (`tempfile` names) | derive the name from the program, not from the temp directory |
| time | 0 | `buildcache.py:152` (`time.time()`), `clockrt.py` | take the clock from `SOURCE_DATE_EPOCH` |
| counter | 0 | `python/pkg-v12/pyfunc.py` (`ctx.tmp += 1` at 1384, 3157) | renumber per function, not per compiler run |
| other | 0 | — | — |

## Why the executable follows the C here

The compile/link command recorded in `native_report.json` is

```
/usr/bin/cc -O2 -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd
   -Werror=implicit-function-declaration -Werror=implicit-int
   -Werror=incompatible-pointer-types -fno-asynchronous-unwind-tables
   -o <TMPDIR>/ailc-XXXXXXXX/program  <TMPDIR>/ailc-XXXXXXXX/program.c
```

There is no `-g` and no `__FILE__`, `__DATE__` or `__TIME__` in the generated C (grep on
`compare/echo_pack`'s 6282-line `program.c`: no hit), the C is always named `program.c` inside the
temp directory so even the assembler `.file` name is constant, and the linker's build-id is a hash
of the contents. The temp directory name therefore appears only in `native_report.json`, never in
the executable: `strings prog | grep -E '/tmp|ailc-|main.py'` finds nothing. That is why all 82
programs with identical C also have identical executables — the binary adds no second source of
difference of its own in this toolchain.

## The 18 programs that were not built

4 compare programs, for the reasons already recorded in `lab/selfhost/DETERMINISM.md`
(`chain_relax`: int64 literal out of range; `rail_transfer`: int64 literal, then an untyped tuple
element; `tally_lang`: `re.match` pos/endpos; `tree_fold`: untyped tuple element and `NODE` used as
a value).

14 stdlib programs: `array/binary_packets.py`, `array/float32_readings.py`,
`array/unicode_codes.py`, `base64/b85_vectors.py`, `base64/legacy_stream_api.py`,
`collections/log_report.py`, `collections/lru_cache.py`, `collections/point_records.py`,
`csv/field_size_limit.py`, `csv/register_dialect.py`, `csv/sniffer.py`,
`datetime/calendar_export.py`, `datetime/epoch_convert.py`, `datetime/iso_week.py`.

Each is a loud, named refusal (the module's coverage tests record the same refusals), not a crash
and not a timeout: a refused program emits no C, so it has no reproducibility result either way.

## Ratchet

`AIL_CURRENT/test_ail_repro.py` (registered in `AIL_CURRENT/tests.d/test_ail_repro.txt`) builds five
of the programs above twice in the same two setups and asserts one sha256 for the executable and one
for `program.c`, and that both builds print the same bytes and exit the same way:
`stdlib/bisect/alias_import.py`, `stdlib/heapq/closest_points.py`,
`examples/tutorial_project/step1.py`, `examples/algos/rpn.py`, `compare/echo_pack`.
It passes in 52 s. When a program with a difference is fixed, add its row here and to `PROGRAMS`;
when the corpus run below is finished, extend `PROGRAMS` from its result.

## Follow-up

- **`ffrepro2`: finish the corpus.** Run `python3 tools/repro_check.py -j 2 --json /tmp/repro.json`
  to completion on an idle runner (467 programs; at the observed 6 programs/min it needs about
  80 minutes) and replace the `measured` row above with the final count. If a `diff` row appears,
  route it with the hook column and name the fix in `DIFFERENCES.md` as `C?-ffrepro2-N`.
- No compiler file was edited by this job: `git diff --stat origin/integ -- AIL_CURRENT` shows only
  the new test module, so the instruction counts of the 10 compare-lab tasks are unchanged by
  construction.

## Reproducing

```
python3 tools/repro_check.py -j 2 --json /tmp/repro.json           # whole corpus
python3 tools/repro_check.py -j 2 --filter compare/                # the 10 compare programs
python3 -B AIL_CURRENT/test_ail_repro.py                           # the ratchet
```
