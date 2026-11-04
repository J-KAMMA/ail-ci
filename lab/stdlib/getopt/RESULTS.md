# `getopt` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/getopt/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3). The programs pass fixed argument lists to
the parser, so they need no command-line arguments of their own.

## Before

Every program was refused at the import. The common first-refusal prefix `P` is:

```
not in the subset: import of 'getopt' is not available: this compiler builds only the modules it
models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path
could not build this program either); general path:
```

| program | default build | first refusal after `P` |
| --- | --- | --- |
| `01_short_options.py` | refused | `getopt.getopt (not yet published in NAMES_library.json)` |
| `02_long_options.py` | refused | `getopt.getopt (not yet published in NAMES_library.json)` |
| `03_prefix_and_double_dash.py` | refused | `getopt.getopt (not yet published in NAMES_library.json)` |
| `04_stop_at_nonoption.py` | refused | `getopt.getopt (not yet published in NAMES_library.json)` |
| `05_gnu_mixed.py` | refused | `getopt.gnu_getopt (not yet published in NAMES_library.json)` |
| `06_gnu_plus.py` | refused | `getopt.gnu_getopt (not yet published in NAMES_library.json)` |
| `07_errors_short.py` | refused | `a caught exception type Attribute (only builtin or user Exception subclasses are supported)` |
| `08_errors_long.py` | refused | `a caught exception type Attribute (only builtin or user Exception subclasses are supported)` |
| `09_error_alias.py` | refused | `a caught exception type Attribute (only builtin or user Exception subclasses are supported)` |
| `10_usage_exit.py` | refused | `a caught exception type Attribute (only builtin or user Exception subclasses are supported)` |
| `11_convert_int.py` | refused | `getopt.getopt (not yet published in NAMES_library.json)` |
| `12_values_and_repeats.py` | refused | `getopt.getopt (not yet published in NAMES_library.json)` |

Result before: **0 built, 0 typed, 12 refused**.

## After

Ten programs build and match CPython in the default build and with `AIL_UNIFIED_FORCE=1`. Every
one uses the general path (the bundled `GetoptError` is a user exception class, which the typed
path does not build). `10_usage_exit.py` writes its usage to stderr and exits 2, as CPython does.

| program | default build | forced general | matches CPython stdout + exit |
| --- | --- | --- | --- |
| `01_short_options.py` | general | general | yes |
| `02_long_options.py` | general | general | yes |
| `03_prefix_and_double_dash.py` | general | general | yes |
| `04_stop_at_nonoption.py` | general | general | yes |
| `05_gnu_mixed.py` | general | general | yes |
| `06_gnu_plus.py` | general | general | yes |
| `07_errors_short.py` | general | general | yes |
| `08_errors_long.py` | general | general | yes |
| `09_error_alias.py` | refused | refused | no (refused; compiler follow-up below) |
| `10_usage_exit.py` | general | general | yes (exit 2) |
| `11_convert_int.py` | general | general | no (`99999999999999999999` is beyond int64) |
| `12_values_and_repeats.py` | general | general | yes |

Result after: **11 built, 0 typed, 1 refused; 10 build and match**. `11_convert_int.py` builds but
stops loudly when `int("99999999999999999999")` overflows int64:

```
OverflowError: integer overflow in int() (ints are 64-bit; --exact-int gives exact ints)
```

Before that value, `42` and `-9223372036854775808` match CPython (including `+ 1`). This is the
documented int64 limit, not a getopt bug.

## Follow-ups (out of scope: compiler files)

* `09_error_alias.py` uses `except getopt.error`, where `error = GetoptError` is a module-level
  name bound to a class. The merge renames it as a variable, so the general path refuses the
  caught exception type. Exact first refusal line:

  ```
  not in the subset: 'msg' is annotated str in the source, but the caller also supplies int; refusing rather than silently choosing one (the general path could not build this program either); general path: a caught exception type getopt.error (only builtin or user Exception subclasses are supported)
  ```

  The same program catches `getopt.GetoptError` successfully in `07_errors_short.py`,
  `08_errors_long.py` and `10_usage_exit.py`; `getopt.error is getopt.GetoptError` is only reached
  as a value in the refused program. A compiler change would have to resolve a module attribute
  that aliases a user exception class in an `except` clause.
