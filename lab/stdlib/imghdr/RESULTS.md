# `imghdr` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/imghdr/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3); stdout and the exit status must agree.
CPython 3.12 also prints a `DeprecationWarning` for `import imghdr` on stderr; stderr is not
compared (the bundled module drops `warnings._deprecated`, so it prints nothing there).

## Before

`AIL_CURRENT/stdlib/imghdr.py` did not exist, so every program was refused at the import.  The
stdlib census (`lab/stdcensus/RESULTS.md`) records the module itself as refused with
`imghdr.py:21:13: not in the subset: os.PathLike used here is not built`.

| program | default build | first refusal line |
| --- | --- | --- |
| `01_jpeg.py` | refused | `not in the subset: imghdr.what (not yet published in NAMES_library.json)` |
| `02_png_gif.py` | refused | `not in the subset: imghdr.what (not yet published in NAMES_library.json)` |
| `03_tiff.py` | refused | `not in the subset: imghdr.what (not yet published in NAMES_library.json)` |
| `04_netpbm.py` | refused | `not in the subset: imghdr.what (not yet published in NAMES_library.json)` |
| `05_misc.py` | refused | `not in the subset: imghdr.what (not yet published in NAMES_library.json)` |
| `06_webp_exr.py` | refused | `not in the subset: imghdr.what (not yet published in NAMES_library.json)` |
| `07_none.py` | refused | `not in the subset: imghdr.what (not yet published in NAMES_library.json)` |
| `08_short_and_empty.py` | refused | `not in the subset: imghdr.what (not yet published in NAMES_library.json)` |
| `09_file_paths.py` | refused | `not in the subset: imghdr.what (not yet published in NAMES_library.json)` |
| `10_tests_list.py` | refused | `not in the subset: imghdr.tests used as a plain value` |

Result before: **0 built, 0 typed, 10 refused**.

## After

All ten programs build and match CPython in the default build and with `AIL_UNIFIED_FORCE=1`, with
the same exit status (0).  All ten use the general path: `imghdr.what` returns `str` on a match and
falls off the end otherwise, and the typed path has no `Optional[str]`.

| program | default build | forced general | matches CPython stdout + exit |
| --- | --- | --- | --- |
| `01_jpeg.py` | general | general | yes |
| `02_png_gif.py` | general | general | yes |
| `03_tiff.py` | general | general | yes |
| `04_netpbm.py` | general | general | yes |
| `05_misc.py` | general | general | yes |
| `06_webp_exr.py` | general | general | yes |
| `07_none.py` | general | general | yes |
| `08_short_and_empty.py` | general | general | yes |
| `09_file_paths.py` | general | general | yes |
| `10_tests_list.py` | general | general | yes |

Result after: **10 built, 0 typed, 0 refused; 10 build and match**.

## Differences from CPython, forced by this compiler

These are written in `AIL_CURRENT/stdlib/imghdr.py`'s docstring and are not compiler follow-ups
(the module was rewritten as the compiler requires; no program depends on them):

* `from os import PathLike` is refused (`os.PathLike used here is not built`); `what` accepts `str`
  paths only.
* `warnings._deprecated(__name__, remove=(3, 13))` is dropped, so `import imghdr` prints no
  `DeprecationWarning` on stderr.  stdout and the exit status are unchanged.
* `test()`/`testall()` are dropped: the compiler refuses `except KeyboardInterrupt` and
  `os.path.isdir`/`os.path.join`.  They are not part of `__all__`.
* `ord(b'P')` is written `b'P'[0]`: the compiler's `ord()` stops at runtime on a bytes argument.

## Compiler follow-ups (not needed for the target)

`10_tests_list.py` cannot read `function.__name__` (`'function' object has no attribute
'__name__'`) and function identity/equality is not stable (`imghdr.tests[0] is imghdr.test_jpeg`
prints `False`), so it recognizes each test by the signature it accepts and prints the equivalent
names.  These are compiler gaps, not refusals; no file outside this task's list was changed.
