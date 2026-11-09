# Third-party notices

This repository contains code copied from, or derived from, third-party
projects. The project itself is licensed under `MIT OR Apache-2.0` (see
`LICENSE-MIT` and `LICENSE-APACHE`).

The table below is the inventory. `File` is a repository-relative path or a
glob; `License file` is a path relative to the repository root, or `-` when
the license text lives with the upstream project. `Notice before` says whether
the file already named its origin and license before this inventory was added.

## Inventory

| File | Origin | License | License file | Notice before |
| --- | --- | --- | --- | --- |
| `AIL_CURRENT/stdlib/chunk.py` | CPython 3.12 `Lib/chunk.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | no |
| `AIL_CURRENT/stdlib/colorsys.py` | CPython 3.12 `Lib/colorsys.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | no |
| `AIL_CURRENT/stdlib/copy.py` | CPython 3.12 `Lib/copy.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | yes |
| `AIL_CURRENT/stdlib/difflib.py` | CPython 3.12 `Lib/difflib.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | origin only |
| `AIL_CURRENT/stdlib/getopt.py` | CPython 3.12 `Lib/getopt.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | no |
| `AIL_CURRENT/stdlib/imghdr.py` | CPython 3.12 `Lib/imghdr.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | origin only |
| `AIL_CURRENT/stdlib/keyword.py` | CPython 3.12 `Lib/keyword.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | origin only |
| `AIL_CURRENT/stdlib/linecache.py` | CPython 3.12 `Lib/linecache.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | origin only |
| `AIL_CURRENT/stdlib/marshal.py` | PyPy `lib_pypy/_marshal.py` @ `ad61ef7d8e42d7bbdec8d41cdd47d908aaa5241e` | MIT | `AIL_CURRENT/stdlib/LICENSE-PYPY-MIT.txt` | yes |
| `AIL_CURRENT/stdlib/netrc.py` | CPython 3.12 `Lib/netrc.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | origin only |
| `AIL_CURRENT/stdlib/quopri.py` | CPython 3.12 `Lib/quopri.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | origin only |
| `AIL_CURRENT/stdlib/sched.py` | CPython 3.12 `Lib/sched.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | no |
| `AIL_CURRENT/stdlib/shlex.py` | CPython 3.12 `Lib/shlex.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | origin only |
| `AIL_CURRENT/stdlib/stat.py` | CPython 3.12 `Lib/stat.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | origin only |
| `AIL_CURRENT/stdlib/struct.py` | AIL's own, written for AIL; behaviour follows CPython 3.12 `Lib/struct.py` | MIT OR Apache-2.0 | `LICENSE-MIT`, `LICENSE-APACHE` | origin named |
| `AIL_CURRENT/stdlib/timeit.py` | CPython 3.12 `Lib/timeit.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | yes |
| `AIL_CURRENT/stdlib/token.py` | CPython 3.12 `Lib/token.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | origin only |
| `AIL_CURRENT/stdlib/xdrlib.py` | CPython 3.12 `Lib/xdrlib.py` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | origin only |
| `AIL_CURRENT/stdlib/tomllib/*.py` | CPython 3.12 `Lib/tomllib/*.py` (upstream `tomli`, Taneli Hukkinen) | MIT (SPDX header in each file) | - | SPDX MIT; origin named |
| `AIL_CURRENT/stdlib/zlib.py` | AIL's own, written over the system zlib; behaviour follows CPython 3.12 `Modules/zlibmodule.c` | MIT OR Apache-2.0 | `LICENSE-MIT`, `LICENSE-APACHE` | origin named |
| `AIL_CURRENT/stdlib/zlib_glue.c` | AIL's own glue; links the system `<zlib.h>`, copies no zlib source | MIT OR Apache-2.0 | `LICENSE-MIT`, `LICENSE-APACHE` | origin named |
| `AIL_CURRENT/stdlib/zlib_glue.h` | AIL's own glue; see `zlib_glue.c` | MIT OR Apache-2.0 | `LICENSE-MIT`, `LICENSE-APACHE` | origin named |
| `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | PSF License Version 2, copied from CPython 3.12's `LICENSE` | PSF-2.0 | `AIL_CURRENT/stdlib/LICENSE-PSF.txt` | is the license |
| `AIL_CURRENT/stdlib/LICENSE-PYPY-MIT.txt` | PyPy `LICENSE` (MIT part with its copyright lines), commit `ad61ef7d8e42d7bbdec8d41cdd47d908aaa5241e` | MIT | `AIL_CURRENT/stdlib/LICENSE-PYPY-MIT.txt` | is the license |
| `third_party/typeshed/LICENSE` | The typeshed project | Apache-2.0 | `third_party/typeshed/LICENSE` | yes |
| `third_party/typeshed/VERSION.md` | The typeshed project (vendored subset record) | Apache-2.0 | `third_party/typeshed/LICENSE` | yes |
| `third_party/typeshed/stdlib/**/*.pyi` | The typeshed project, commit `bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272` | Apache-2.0 | `third_party/typeshed/LICENSE` | yes |
| `AIL_CURRENT/python/pkg-v12/stubsigs_table.py` | Generated from `third_party/typeshed` by `tools/typeshed_convert.py` | Apache-2.0 | `third_party/typeshed/LICENSE` | origin only (license not named) |

Counts:

- 20 files derived from CPython under `AIL_CURRENT/stdlib/` (16 modules plus
  the 4 files of `tomllib/`). All 20 carry a notice in their module docstring.
- 1 file derived from PyPy (`marshal.py`), with the PyPy MIT text beside it.
- 50 files under `third_party/typeshed` (48 `stdlib/**/*.pyi` stubs plus
  `LICENSE` and `VERSION.md`), all under Apache-2.0 with the license beside
  them.
- 4 files under `AIL_CURRENT/stdlib/` are AIL's own (`zlib.py`,
  `zlib_glue.c`, `zlib_glue.h`, `struct.py`); they link the system zlib or
  implement the behaviour themselves, they do not copy upstream source.
- 2 files under `AIL_CURRENT/stdlib/` are license texts (`LICENSE-PSF.txt`,
  `LICENSE-PYPY-MIT.txt`).
- Total files under `AIL_CURRENT/stdlib/` and `third_party/`: 77, of which 71
  are third-party or derived (20 CPython-derived, 1 PyPy-derived, 50 typeshed,
  and 2 license texts) and 4 are AIL's own. 0 files are without a notice.
- These counts describe the tree when this inventory was last updated.
  `AIL_CURRENT/test_ail_third_party_notices.py` does not compare them: it
  checks that every file under `AIL_CURRENT/stdlib/` and `third_party/` has a
  row, so a newly bundled file fails the test until its row is added here.

## Unchanged generated data

`AIL_CURRENT/python/pkg-v12/cruntime.py` contains Unicode tables generated by
`tools/gen_casemap.py` and `tools/gen_strprops.py` from the running CPython
3.12's own `str` methods. They are data derived from CPython (PSF-2.0) inside
an AIL-owned file; no separate file is vendored.

`AIL_CURRENT/python/pkg-v12/stararity.py` holds argument-count `TypeError`
message templates re-derived from CPython 3.12's built-in methods. They are
data derived from CPython (PSF-2.0) inside an AIL-owned file; no separate file
is vendored. `AIL_CURRENT/python/pkg-v12/stubsigs_table.py` is generated from
the vendored `third_party/typeshed` by `tools/typeshed_convert.py` and is
listed in the inventory above.

## Follow-ups

- The `ailc` wheel does not yet carry the PSF notice. `packaging/ail_wheel_backend.py`
  is owned by another lane; it needs this exact change. After
  `LICENSE_FILES = ("LICENSE-APACHE", "LICENSE-MIT")` (line ~43) add
  `PSF_LICENSE = "AIL_CURRENT/stdlib/LICENSE-PSF.txt"`, and in `collect()` after
  the `for name in LICENSE_FILES:` loop add
  `entries[info + "/licenses/LICENSE-PSF.txt"] = (REPO / PSF_LICENSE).read_bytes()`,
  and in `prepare_metadata_for_build_wheel()` after its `for name in LICENSE_FILES:` loop add
  `(info / "licenses" / "LICENSE-PSF.txt").write_bytes((REPO / PSF_LICENSE).read_bytes())`.
  Do not add `LICENSE-PSF.txt` to the manifest's `sdk_files`: `test_ail_packaging`
  checks the wheel file list against that selection, and the notice belongs under
  `.dist-info/licenses/`, not in the SDK tree.
  Until that change lands `test_ail_third_party_notices` accepts the missing PSF wheel
  entry only because this paragraph exists; remove this paragraph when it lands.
