# `mailcap` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/mailcap/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3).  Only stdout and the exit status are
compared: CPython prints a `DeprecationWarning` for `import mailcap` (and one for
`readmailcapfile`); this compiler does not build the `warnings` module, so the bundled module
writes warning text to stderr instead.  Every program writes its own mailcap file in the
current directory.

## Before

Every program was refused at the import and there was no `AIL_CURRENT/stdlib/mailcap.py`.  The
common first line is:

```
<program>.py:1:1: not in the subset: import of 'mailcap' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: mailcap.<function> (not yet published in NAMES_library.json)
```

| program | default build | first refusal |
| --- | --- | --- |
| `01_parse_basic.py` | refused | `mailcap.getcaps (not yet published in NAMES_library.json)` |
| `02_continuation.py` | refused | `mailcap.getcaps (not yet published in NAMES_library.json)` |
| `03_lineno.py` | refused | `mailcap.getcaps (not yet published in NAMES_library.json)` |
| `04_lookup_plain.py` | refused | `mailcap.getcaps (not yet published in NAMES_library.json)` |
| `05_lookup_wildcard.py` | refused | `mailcap.getcaps (not yet published in NAMES_library.json)` |
| `06_missing_type.py` | refused | `mailcap.getcaps (not yet published in NAMES_library.json)` |
| `07_findmatch_no_test.py` | refused | `mailcap.getcaps (not yet published in NAMES_library.json)` |
| `08_findmatch_plist.py` | refused | `mailcap.getcaps (not yet published in NAMES_library.json)` |
| `09_subst_direct.py` | refused | `mailcap.subst (not yet published in NAMES_library.json)` |
| `10_unsafe_filename.py` | refused | `mailcap.getcaps (not yet published in NAMES_library.json)` |

Result before: **0 built, 0 typed, 10 refused**.

## After

All ten programs build (on the general path, the only path that builds file I/O and a dict
mixing `str` values with the integer `lineno`) and match CPython's stdout and exit status in the
default build and with `AIL_UNIFIED_FORCE=1`.  `09_subst_direct.py` ends with a lone `%`, where
CPython raises IndexError inside `subst`; the compiled program raises the same named error and
exits 1 with the same stdout, so it matches.

| program | default build | forced general | matches CPython stdout + exit |
| --- | --- | --- | --- |
| `01_parse_basic.py` | general | general | yes |
| `02_continuation.py` | general | general | yes |
| `03_lineno.py` | general | general | yes |
| `04_lookup_plain.py` | general | general | yes |
| `05_lookup_wildcard.py` | general | general | yes |
| `06_missing_type.py` | general | general | yes |
| `07_findmatch_no_test.py` | general | general | yes |
| `08_findmatch_plist.py` | general | general | yes |
| `09_subst_direct.py` | general | general | yes (exit 1 after the same stdout) |
| `10_unsafe_filename.py` | general | general | yes |

Result after: **10 built, 0 typed, 0 refused; 10 build and match**.

## Differences recorded in `AIL_CURRENT/stdlib/mailcap.py`

* `warnings` is not a bundled module, so `_warn` writes the same text plus a newline to
  stderr.  `readmailcapfile`'s deprecation message and both `UnsafeMailcapInput` refusals are
  written that way.  CPython's `import mailcap` DeprecationWarning is not emitted.
* `UnsafeMailcapInput` derives from `Exception`: the compiler does not build a class whose
  base is the builtin `Warning`.  CPython only raises it as a warning; mailcap never catches it.
* `os.system` is not built on either compiler path, so an entry carrying a `test=` field raises
  `OSError` with a clear message instead of running the command.  No lab program uses `test=`.
* `os.pathsep` is not built as a value, so `listmailcapfiles` splits `MAILCAPS` on `":"` (the
  POSIX separator this platform uses).
