# `linecache` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/linecache/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3), run in the same working directory. The
programs find their input files through `os.path.dirname(__file__)` + `data/<name>`; the one
program that rewrites a file does so in its working directory and removes it again.
`AIL_UNIFIED_FORCE=1` is the forced-general build.

## Before

`AIL_CURRENT/stdlib/linecache.py` did not exist, so every program was refused at its first call.
All ten were refused with this common text (column and program differ):

```
<program>.py:<line>:<col>: not in the subset: linecache.getline (not yet published in NAMES_library.json)
```

| program | default build | first refusal |
| --- | --- | --- |
| `01_first_line.py` | refused | `7:1: linecache.getline (not yet published in NAMES_library.json)` |
| `02_middle_line.py` | refused | `8:5: linecache.getline (not yet published in NAMES_library.json)` |
| `03_last_line.py` | refused | `7:1: linecache.getlines (not yet published in NAMES_library.json)` |
| `04_out_of_range.py` | refused | `8:5: linecache.getline (not yet published in NAMES_library.json)` |
| `05_missing_file.py` | refused | `7:1: linecache.getline (not yet published in NAMES_library.json)` |
| `06_getlines.py` | refused | `8:1: linecache.getlines (not yet published in NAMES_library.json)` |
| `07_clearcache.py` | refused | `8:1: linecache.getline (not yet published in NAMES_library.json)` |
| `08_checkcache_rewrite.py` | refused | `7:1: linecache.getline (not yet published in NAMES_library.json)` |
| `09_no_final_newline.py` | refused | `7:1: linecache.getline (not yet published in NAMES_library.json)` |
| `10_utf8.py` | refused | `8:5: linecache.getline (not yet published in NAMES_library.json)` |

Result before: **0 built, 0 typed, 10 refused**.

## After

All ten build and match CPython's stdout and exit status in the default build and with
`AIL_UNIFIED_FORCE=1`. Every one takes the general path (the merger reports `linecache.getline
returns a str on one path and something else on another`), as `getopt` does.

| program | default build | forced general | matches CPython stdout + exit |
| --- | --- | --- | --- |
| `01_first_line.py` | general | general | yes |
| `02_middle_line.py` | general | general | yes |
| `03_last_line.py` | general | general | yes |
| `04_out_of_range.py` | general | general | yes |
| `05_missing_file.py` | general | general | yes |
| `06_getlines.py` | general | general | yes |
| `07_clearcache.py` | general | general | yes |
| `08_checkcache_rewrite.py` | general | general | yes |
| `09_no_final_newline.py` | general | general | yes |
| `10_utf8.py` | general | general | yes |

Result after: **10 built, 0 typed, 0 refused; 10 build and match**.

## Behaviour differences (documented in the module docstring)

* `encoding="utf-8"` instead of `tokenize.open`, so a PEP 263 coding cookie and a UTF-8 BOM are
  not honoured; a file that is not UTF-8 gives the empty result.
* `checkcache` compares content, because `os.stat` is not built (it re-reads and compares the
  line list); CPython compares `st_size` and `st_mtime`. `08_checkcache_rewrite.py` changes the
  file's size as well, so both implementations drop the entry.
* The cache entry keeps CPython's `(size, mtime, lines, fullname)` shape with `size` the number
  of characters read and `mtime` always `0` (`None` inside a tuple is not built).
* No `sys.path` search for a relative filename that is not in the working directory.
* `lazycache` and the `module_globals` loader path are dropped (no module loader); the argument
  is accepted and ignored.

## Follow-ups

None: no compiler file needs to change.
