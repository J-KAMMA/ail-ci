# Third-party notices

This repository contains code copied or derived from third-party projects. The
table below is the complete inventory of files under `third_party/` and
`AIL_CURRENT/stdlib/`; it is checked by
`AIL_CURRENT/test_ail_third_party_notices.py`.

Counts:

- CPython 3.12 derived files: 11 (PSF License Version 2)
- typeshed files: 50, of which 48 are vendored stubs (Apache License 2.0)
- AIL's own files under `AIL_CURRENT/stdlib/`: 3 (MIT OR Apache-2.0)
- license texts under `AIL_CURRENT/stdlib/`: 1 (`LICENSE-PSF.txt`)

## Origins

### CPython 3.12 standard library

- License: Python Software Foundation License Version 2 (PSF-2.0)
- License file: `AIL_CURRENT/stdlib/LICENSE-PSF.txt`
- Upstream: https://github.com/python/cpython (3.12 branch, `Lib/`)
- Status: AIL source copies or ports. Each derived file carries a first-lines
  notice naming `LICENSE-PSF.txt`; the rewrites are documented in the module
  docstrings and in `lab/stdlib/<module>/RESULTS.md`.

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

## Follow-ups

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
