# `ail run --diff` census

Every program is built once and run twice (natively, then under CPython) with the same input, through `ail run --diff --json`; the outcomes are the command's own. A **differ** means the compiler and CPython disagree, which is a bug in one of them (usually the compiler); this census only lists them.

## lab/compare/src/*/main.py, public cases

| outcome | count |
| --- | --- |
| agree | 17 |
| differ | 4 |
| loud stop by design | 9 |
| **total** | **30** |

Ten programs, every public case of the task's `gen.py`, run as the task runs them (stdin when the task reads stdin, both builds' arguments).

### Differ (a bug list for the compiler; not fixed here)

| program | what differed |
| --- | --- |
| `chain_relax/bad_n` | the build stopped where CPython exited 1: main.py:27:27: int64 literal out of range: 18446744073709551615 |
| `tally_lang/parse_error` | the build stopped where CPython exited 2: main.py:411:5: not in the subset: field `v` is a list or dict that gets bools and numbers (Python keeps each element's own type) (the general path could not build this program either); general path: n... |
| `tally_lang/runtime_error` | the build stopped where CPython exited 3: main.py:411:5: not in the subset: field `v` is a list or dict that gets bools and numbers (Python keeps each element's own type) (the general path could not build this program either); general path: n... |
| `tree_fold/malformed` | the build stopped where CPython exited 1: main.py:2:1: not in the subset: import of 're' with a use that is not built: the re module is built for string- or bytes-literal patterns only (match, fullmatch, search, findall, finditer, split, sub,... |

### Loud stop by design

| program | reason |
| --- | --- |
| `chain_relax/small` | main.py:27:27: int64 literal out of range: 18446744073709551615 |
| `chain_relax/one_element` | main.py:27:27: int64 literal out of range: 18446744073709551615 |
| `rail_transfer/small` | main.py:55:5: not in the subset: a constant integer expression overflows int64: its exact value is outside the signed 64-bit range and does not fit in a 64-bit signed integer (CPython computes it exac... |
| `rail_transfer/tie_on_time` | main.py:55:5: not in the subset: a constant integer expression overflows int64: its exact value is outside the signed 64-bit range and does not fit in a 64-bit signed integer (CPython computes it exac... |
| `rail_transfer/random_small` | main.py:55:5: not in the subset: a constant integer expression overflows int64: its exact value is outside the signed 64-bit range and does not fit in a 64-bit signed integer (CPython computes it exac... |
| `scar_life/small` | OverflowError: integer overflow in int() (ints are 64-bit; --exact-int gives exact ints) |
| `tally_lang/example` | main.py:411:5: not in the subset: field `v` is a list or dict that gets bools and numbers (Python keeps each element's own type) (the general path could not build this program either); general path: n... |
| `tree_fold/example` | main.py:2:1: not in the subset: import of 're' with a use that is not built: the re module is built for string- or bytes-literal patterns only (match, fullmatch, search, findall, finditer, split, sub,... |
| `tree_fold/prune_cut` | main.py:2:1: not in the subset: import of 're' with a use that is not built: the re module is built for string- or bytes-literal patterns only (match, fullmatch, search, findall, finditer, split, sub,... |


## 50 corpus/gdev programs

| outcome | count |
| --- | --- |
| agree | 46 |
| differ | 1 |
| loud stop by design | 3 |
| **total** | **50** |

The first programs of `corpus/gdev` in name order, no arguments and empty stdin.

### Differ (a bug list for the compiler; not fixed here)

| program | what differed |
| --- | --- |
| `corpus/g01_008.py` | stdout line 1: native '', cpython 'Parsed entries: 6' |

### Loud stop by design

| program | reason |
| --- | --- |
| `corpus/g01_020.py` | g01_020.py:14:5: not in the subset: urllib.parse.parse_qs is not built. Built: urllib.request.urlopen(url or Request, data=None, timeout=) and urllib.request.Request(url, data=None, headers={}, method... |
| `corpus/g01_032.py` | g01_032.py:277:9: not in the subset: next() of a _AilCsvReader instance (the iterator protocol is not built) (the general path could not build this program either); general path: the method .search() ... |
| `corpus/g02_010.py` | g02_010.py:10:5: not in the subset: math.factorial() of constants makes a value beyond int64, and AIL ints are 64-bit by default (the program needs a big int here). |

