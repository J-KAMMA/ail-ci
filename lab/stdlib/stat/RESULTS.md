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

Filled in after the bundled module was added (see the end of this file).

## What the module does

`AIL_CURRENT/stdlib/stat.py` is CPython 3.12's `Lib/stat.py` as AIL source. Every public name and
value is kept (the `ST_*` indices, `S_IMODE`, `S_IFMT`, the `S_IF*`/`S_I*` constants, the
`S_IS*` predicates, `UF_*`/`SF_*`, `FILE_ATTRIBUTE_*`, `filemode`). The trailing
`from _stat import *` is dropped because there is no C `_stat` module in a single-file program.

CPython's `_filemode_table` is a module-level tuple of tuples of (int, str); the typed path refuses
that ("module-level list of non-numbers"), which is why the stdlib census built `stat` on the
general path. `filemode` is rewritten as an explicit `if` chain over the same bits, so no table of
mixed values exists at module scope. The output is identical for every mode.
