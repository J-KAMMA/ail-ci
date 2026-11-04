# `stat` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/stat/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 -B <program>.py` (CPython 3.12.3). The programs use only fixed mode
integers (no `os.stat`, which is not built) so they need no arguments and no files.

## Before

Every program was refused at the import. The common first-refusal prefix `P` is:

```
not in the subset: import of 'stat' is not available: this compiler builds only the modules it
models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path
could not build this program either); general path:
```

| program | default build | first refusal after `P` |
| --- | --- | --- |
| `01_file_kinds.py` | refused | `stat.S_ISDIR (not yet published in NAMES_library.json)` |
| `02_imode_ifmt.py` | refused | `stat.S_IFMT (not yet published in NAMES_library.json)` |
| `03_filemode_basic.py` | refused | `stat.filemode (not yet published in NAMES_library.json)` |
| `04_special_bits.py` | refused | `stat.filemode (not yet published in NAMES_library.json)` |
| `05_permission_constants.py` | refused | `stat.S_IRUSR used as a plain value` |
| `06_stat_indices.py` | refused | `stat.ST_MODE used as a plain value` |
| `07_flags.py` | refused | `stat.UF_NODUMP used as a plain value` |
| `08_filemode_loop.py` | refused | `stat.filemode (not yet published in NAMES_library.json)` |
| `09_beyond_int64.py` | refused | `stat.filemode (not yet published in NAMES_library.json)` |
| `10_filemode_expected.py` | refused | `stat.filemode (not yet published in NAMES_library.json)` |
| `11_kind_names.py` | refused | `stat.S_ISDIR (not yet published in NAMES_library.json)` |
| `12_permission_report.py` | refused | `stat.S_IRUSR used as a plain value` |

Result before: **0 built, 0 typed, 12 refused**.

## After

All twelve programs build and reach the **typed** path with the bundled `stat.py`, in the default
build, with `AIL_UNIFIED_FORCE=1`, and with `--strict`. Eleven match CPython's stdout and exit
status in both builds. `09_beyond_int64.py` builds typed but stops loudly when the runtime int64
multiplication overflows (CPython's ints are unbounded, then its C `_stat.filemode` raises the
`OverflowError` the program catches).

| program | default build | forced general | `--strict` | matches CPython stdout + exit |
| --- | --- | --- | --- | --- |
| `01_file_kinds.py` | typed | general | builds | yes |
| `02_imode_ifmt.py` | typed | general | builds | yes |
| `03_filemode_basic.py` | typed | general | builds | yes |
| `04_special_bits.py` | typed | general | builds | yes |
| `05_permission_constants.py` | typed | general | builds | yes |
| `06_stat_indices.py` | typed | general | builds | yes |
| `07_flags.py` | typed | general | builds | yes |
| `08_filemode_loop.py` | typed | general | builds | yes |
| `09_beyond_int64.py` | typed | general | builds | no (loud int64 overflow) |
| `10_filemode_expected.py` | typed | general | builds | yes |
| `11_kind_names.py` | typed | general | builds | yes |
| `12_permission_report.py` | typed | general | builds | yes |

Result after: **12 built, 12 typed, 0 refused; 11 build and match** (target: 10 built and matching,
8 typed).

The loud stop for `09_beyond_int64.py` on the default build is:

```
OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)
  raised near lab/stdlib/stat/09_beyond_int64.py:9
```

CPython prints its `mode`, then catches the `_stat.filemode` `OverflowError`:
`mode 2361183241434822606848` / `error name OverflowError` / `done`.

## Speed probe

`08_filemode_loop.py` computes a checksum over `filemode` strings for all 4096 permission values.
The intended measurement is `tools/icount.c` on CPython, the typed build and the census-style
general-path build (CPython's original `Lib/stat.py` copied into a temp directory). This runner
refuses the perf event, so the instruction counts could not be taken:

```
$ /tmp/icount python3 -B lab/stdlib/stat/08_filemode_loop.py
perf_event_open: Permission denied
```

The old module text reproduces the census result exactly:

```
note: stat.py:128:1: built on the general path (about 20x slower) because 'stat._filemode_table'
is a module-level list of non-numbers; ... run with --strict to see why
```

As a substitute, 200 whole-process runs each (`/usr/bin/time`, same runner, `/dev/null` output):

| build | 200 runs real | 200 runs user |
| --- | ---: | ---: |
| CPython 3.12.3 | 4.61 s | 3.67 s |
| typed (bundled `stat.py`) | 0.29 s | 0.16 s |
| general path (CPython `stat.py`) | 2.78 s | 1.82 s |

Process startup is included, so these are a lower bound on the speedup; the typed loop is about
9.6x faster than the general path in this proxy. No `icount` numbers are claimed.

## What the module does

`AIL_CURRENT/stdlib/stat.py` is CPython 3.12's `Lib/stat.py` as AIL source. Every public name and
value is kept (the `ST_*` indices, `S_IMODE`, `S_IFMT`, the `S_IF*`/`S_I*` constants, the
`S_IS*` predicates, `UF_*`/`SF_*`, `FILE_ATTRIBUTE_*`, `filemode`). The trailing
`from _stat import *` is dropped because there is no C `_stat` module in a single-file program.

CPython's `_filemode_table` is a module-level tuple of tuples of (int, str); the typed path refuses
that ("module-level list of non-numbers"), which is why the stdlib census built `stat` on the
general path. `filemode` is rewritten as an explicit `if` chain over the same bits, so no table of
mixed values exists at module scope. The output is identical for every mode.

CPython 3.12's `stat` is the C `_stat` module (`from _stat import *`); its `S_IMODE`, `S_IFMT`,
`S_IS*` and `filemode` take the mode as an unsigned 32-bit int, so a negative mode or one above
`0xFFFFFFFF` raises `OverflowError` and an unknown file type prints `?`. The bundled functions do
the same (`_check_mode`). The pure-Python fallbacks in `Lib/stat.py` would instead compute on a
negative int and print `-` for an unknown type; they are not what CPython exposes. Everything is
checked against CPython for `range(0, 0o200000)` and at the domain edges by
`AIL_CURRENT/test_ail_std_stat.py`.
