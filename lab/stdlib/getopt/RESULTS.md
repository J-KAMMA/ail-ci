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

_To be filled in after the bundled module and test are in place._
