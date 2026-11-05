# Third-party notices

This repository contains code copied or derived from third-party projects. The
table below is the complete inventory of files under `third_party/` and
`AIL_CURRENT/stdlib/`; it is checked by
`AIL_CURRENT/test_ail_third_party_notices.py`.

Counts:

- CPython 3.12 derived files under `AIL_CURRENT/stdlib/`: 11 (PSF License
  Version 2), all with the notice
- CPython-derived compiler preludes outside that directory: 2 (PSF License
  Version 2), notice pending (see "Follow-ups")
- typeshed files: 50, of which 48 are vendored stubs (Apache License 2.0)
- AIL's own files under `AIL_CURRENT/stdlib/`: 3 (MIT OR Apache-2.0)
- license texts under `AIL_CURRENT/stdlib/`: 1 (`LICENSE-PSF.txt`)
- derived files outside those directories with a source note in their
  docstring: 2 generated tables (listed under "Generated tables" below)

## Origins

### CPython 3.12 standard library

- License: Python Software Foundation License Version 2 (PSF-2.0)
- License file: `AIL_CURRENT/stdlib/LICENSE-PSF.txt`
- Upstream: https://github.com/python/cpython (3.12 branch, `Lib/`)
- Status: AIL source copies or ports. Each derived file carries a first-lines
  notice naming `LICENSE-PSF.txt`; the rewrites are documented in the module
  docstrings and in `lab/stdlib/<module>/RESULTS.md`.

### CPython 3.12 compiler preludes

- License: Python Software Foundation License Version 2 (PSF-2.0)
- License file: `AIL_CURRENT/stdlib/LICENSE-PSF.txt`
- Upstream: https://github.com/python/cpython (3.12 branch)
- Status: `AIL_CURRENT/python/pkg-v12/prelude_csv.py` is a port of
  `Modules/_csv.c`; `AIL_CURRENT/python/pkg-v12/prelude_format.py` is a port
  of `Objects/stringlib/unicode_format.h`. Both ship in the `ailc` wheel.
  Their first-lines PSF notice has not been added yet: the original task limits
  docstring edits to `AIL_CURRENT/stdlib/`, so the two files are carried with
  `Notice` = no plus the exact line for the owning lane under "Follow-ups".

### typeshed

- License: Apache License 2.0
- License file: `third_party/typeshed/LICENSE`
- Upstream: https://github.com/python/typeshed
- Commit: `bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272` (see
  `third_party/typeshed/VERSION.md`)
- Status: vendored stub files, copied unchanged.

### AIL's own files under `AIL_CURRENT/stdlib/`

- License: MIT OR Apache-2.0 (the project license)
- `zlib.py` is AIL source written over the C FFI; `zlib_glue.c` and
  `zlib_glue.h` are AIL's glue. They call the system zlib library and mirror
  CPython's `zlibmodule.c` behaviour, but they copy no zlib or CPython source
  text.
- `LICENSE-PSF.txt` is the upstream PSF license text, copied verbatim from
  CPython 3.12's `LICENSE`.

### Generated tables

Two files elsewhere in the tree are generated from third-party material. They
are not under the two directories the inventory table covers, so they are listed
here; both already carry a source note in their docstring.

- `AIL_CURRENT/python/pkg-v12/stubsigs_table.py`: written by
  `tools/typeshed_convert.py` from `third_party/typeshed` (Apache License 2.0,
  `third_party/typeshed/LICENSE`; see `third_party/typeshed/VERSION.md`).
- `AIL_CURRENT/python/pkg-v12/stararity.py`: tables of CPython 3.12's
  `TypeError` text for built-in methods, observed from the interpreter. No
  CPython source text is copied; any message text it reproduces is covered by
  CPython's PSF License Version 2 (`AIL_CURRENT/stdlib/LICENSE-PSF.txt`).

Besides the entries above, the "port of CPython" sweep that found the two
preludes matches two modules that only describe them:
`AIL_CURRENT/python/pkg-v12/csvgen.py` installs `prelude_csv.py` and
`AIL_CURRENT/python/pkg-v12/fmtlib.py` installs `prelude_format.py`. Neither
contains copied third-party source.
`AIL_CURRENT/stdlib/zlib_glue.c` and `zlib_glue.h` are AIL's own glue over the
system zlib library; they copy no zlib source.

## Inventory

| File | Origin | License | Notice |
| --- | --- | --- | --- |
| `third_party/typeshed/LICENSE` | typeshed (upstream) | Apache-2.0 | yes |
| `third_party/typeshed/VERSION.md` | AIL vendor record | MIT OR Apache-2.0 | yes |
| `third_party/typeshed/stdlib/_bisect.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/_csv.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/_decimal.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/_hashlib.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/_heapq.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/_io.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/_operator.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/_random.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/abc.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/array.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/base64.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/bisect.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/builtins.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/calendar.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/collections/__init__.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/csv.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/datetime.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/decimal.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/enum.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/fractions.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/functools.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/genericpath.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/graphlib.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/hashlib.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/heapq.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/html/__init__.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/io.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/ipaddress.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/itertools.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/json/__init__.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/keyword.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/math/__init__.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/numbers.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/operator.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/os/__init__.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/os/path.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/posixpath.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/pprint.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/random.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/re.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/shlex.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/sqlite3/__init__.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/statistics.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/string/__init__.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/sys/__init__.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/time.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/unicodedata.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `third_party/typeshed/stdlib/zlib.pyi` | typeshed bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272 | Apache-2.0 | yes |
| `AIL_CURRENT/stdlib/colorsys.py` | CPython 3.12 (Lib/colorsys.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/difflib.py` | CPython 3.12 (Lib/difflib.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/getopt.py` | CPython 3.12 (Lib/getopt.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/keyword.py` | CPython 3.12 (Lib/keyword.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/shlex.py` | CPython 3.12 (Lib/shlex.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/stat.py` | CPython 3.12 (Lib/stat.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/token.py` | CPython 3.12 (Lib/token.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/tomllib/__init__.py` | CPython 3.12 (Lib/tomllib/__init__.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/tomllib/_parser.py` | CPython 3.12 (Lib/tomllib/_parser.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/tomllib/_re.py` | CPython 3.12 (Lib/tomllib/_re.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/tomllib/_types.py` | CPython 3.12 (Lib/tomllib/_types.py) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | Python Software Foundation (license text) | PSF-2.0 | yes |
| `AIL_CURRENT/stdlib/zlib.py` | AIL | MIT OR Apache-2.0 | yes |
| `AIL_CURRENT/stdlib/zlib_glue.c` | AIL | MIT OR Apache-2.0 | yes |
| `AIL_CURRENT/stdlib/zlib_glue.h` | AIL | MIT OR Apache-2.0 | yes |
| `AIL_CURRENT/python/pkg-v12/prelude_csv.py` | CPython 3.12 (Modules/_csv.c) | PSF-2.0 | no |
| `AIL_CURRENT/python/pkg-v12/prelude_format.py` | CPython 3.12 (Objects/stringlib/unicode_format.h) | PSF-2.0 | no |

## Follow-ups

- `AIL_CURRENT/python/pkg-v12/prelude_csv.py` and
  `AIL_CURRENT/python/pkg-v12/prelude_format.py` are CPython 3.12 ports that
  ship in the wheel without a PSF notice. The task that created this inventory
  limits docstring edits to `AIL_CURRENT/stdlib/`, so the notice belongs to the
  lane that owns `python/pkg-v12`. Add this line to the first comment block of
  each file, naming the source shown in the inventory row:

  ```python
  # Derived from CPython 3.12 <source>; PSF License, see stdlib/LICENSE-PSF.txt.
  ```

  `<source>` is `Modules/_csv.c` for `prelude_csv.py` and
  `Objects/stringlib/unicode_format.h` for `prelude_format.py`. Once added, set
  the `Notice` column for both rows to `yes`; the notices test then requires the
  line and `LICENSE-PSF.txt` in the first 15 lines.

The wheel backend (`packaging/ail_wheel_backend.py`, owned by another lane)
currently ships only the two root licenses. To complete the PSF notice in the
published `ailc` wheel, change the license copy loop in `collect()` from:

```python
    for name in LICENSE_FILES:
        entries["%s/licenses/%s" % (info, name)] = (REPO / name).read_bytes()
```

to:

```python
    for name in LICENSE_FILES:
        entries["%s/licenses/%s" % (info, name)] = (REPO / name).read_bytes()
    entries["%s/licenses/LICENSE-PSF.txt" % info] = (SOURCE / "stdlib" / "LICENSE-PSF.txt").read_bytes()
    entries["%s/licenses/LICENSE-typeshed.txt" % info] = (REPO / "third_party" / "typeshed" / "LICENSE").read_bytes()
```

Until that lands, `test_ail_third_party_notices.py` reports the missing
`LICENSE-PSF.txt` in the wheel as a test failure, not a skip.

Two further files decide what an exported SDK carries, and both are owned by
other lanes. `tools/update_manifest.py` marks an SDK file only when it ends in
`.py`, `.c` or `.h` (`sdk_source()` and `is_compiler_source()`), so
`AIL_CURRENT/stdlib/LICENSE-PSF.txt` cannot be pinned as one; widening those
suffix sets would carry it under `ail_lang/sdk/stdlib/`. The `collect()`
change above is enough for the wheel check as written.
