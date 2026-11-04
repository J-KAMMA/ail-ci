# `difflib` lab results

Twelve ordinary Python programs, each compiled with the default command
(`python3 -B AIL_CURRENT/ail_chatgpt.py compile X.py -o OUT`) and compared with
CPython 3.12's stdout and exit status.  The after rows were also checked with
`AIL_UNIFIED_FORCE=1`.

## Before (integ `staging:integ`, export commit `327abd3`)

All twelve were refused: there was no bundled `stdlib/difflib.py`, so
`import difflib` did not resolve on either path.  The first refusal line was the
same shape in every program; the general-path suffix named the first missing
name.

| Program | Typed path | General path | First refusal (general-path suffix) |
|---|---|---|---|
| `01_close_matches.py` | refused | refused | `difflib.get_close_matches (not yet published in NAMES_library.json)` |
| `02_config_typo.py` | refused | refused | `difflib.get_close_matches (not yet published in NAMES_library.json)` |
| `03_patch_preview.py` | refused | refused | `difflib.unified_diff (not yet published in NAMES_library.json)` |
| `04_unified_edges.py` | refused | refused | `a **kwargs call argument` |
| `05_context_patch.py` | refused | refused | `difflib.context_diff (not yet published in NAMES_library.json)` |
| `06_ndiff_restore.py` | refused | refused | `difflib.ndiff (not yet published in NAMES_library.json)` |
| `07_differ_junk.py` | refused | refused | `difflib.Differ (not yet published in NAMES_library.json)` |
| `08_seq_ratio.py` | refused | refused | `difflib.SequenceMatcher (not yet published in NAMES_library.json)` |
| `09_seq_opcodes.py` | refused | refused | `difflib.SequenceMatcher (not yet published in NAMES_library.json)` |
| `10_seq_grouped.py` | refused | refused | `difflib.SequenceMatcher (not yet published in NAMES_library.json)` |
| `11_diff_bytes.py` | refused | refused | `difflib.diff_bytes (not yet published in NAMES_library.json)` |
| `12_htmldiff.py` | refused | refused | `difflib.HtmlDiff (not yet published in NAMES_library.json)` |

The complete typed refusal for `01` started:

```
01_close_matches.py:1:1: not in the subset: import of 'difflib' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: difflib.get_close_matches (not yet published in NAMES_library.json)
```

## After (bundled `AIL_CURRENT/stdlib/difflib.py`)

Ten of the twelve programs build and match CPython byte for byte in both the
default build and with `AIL_UNIFIED_FORCE=1`.  The default build falls back to
the general path for every program that imports `difflib` (the note names
`difflib.SequenceMatcher.__init__` and its default arguments); the forced build
takes the same general path directly.

| Program | Default build | `AIL_UNIFIED_FORCE=1` | Note |
|---|---|---|---|
| `01_close_matches.py` | general, matches | matches | |
| `02_config_typo.py` | general, matches | matches | |
| `03_patch_preview.py` | general, matches | matches | |
| `04_unified_edges.py` | **refused** | **refused** | follow-up 1 |
| `05_context_patch.py` | general, matches | matches | |
| `06_ndiff_restore.py` | general, matches | matches | |
| `07_differ_junk.py` | general, matches | matches | |
| `08_seq_ratio.py` | general, matches | matches | |
| `09_seq_opcodes.py` | general, matches | matches | |
| `10_seq_grouped.py` | general, matches | matches | |
| `11_diff_bytes.py` | general, matches | matches | |
| `12_htmldiff.py` | **refused** | **refused** | follow-up 2 |

## Speed (bench_ratio.py)

Two lists of 3000 lines from the fixed LCG in `bench_ratio.py`, with every tenth
line in the second list changed; the program prints `ratio()` and the number of
opcodes (`0.9`, `600`).  Build with `AIL_NO_CACHE=1`, then run times only, median
of three.  The AIL build took the general path.

| Version | Run times (s) | Median (s) |
|---|---|---|
| `python3` 3.12.3 | 0.1712, 0.1655, 0.1935 | 0.1712 |
| AIL (general path) | 0.2205, 0.2156, 0.2154 | 0.2156 |

## Follow-ups (out of scope here)

1. `04_unified_edges.py`: the program itself uses a `**kwargs` call argument to
   forward options to `unified_diff`.  The general path refuses it before the
   module is involved; this needs a compiler change, not a `difflib.py` change.

   ```
   04_unified_edges.py:5:5: not in the subset: a **kwargs call argument
   ```

   The default (typed-first) build reports the same general-path refusal after
   its own note about `difflib.unified_diff.__iter__`.

2. `12_htmldiff.py`: `HtmlDiff` is intentionally not part of the bundled module
   (neither is the private `_mdiff`).  The refusal is by name:

   ```
   12_htmldiff.py:7:13: module 'difflib' has no top-level name 'HtmlDiff' (it defines: Differ, IS_CHARACTER_JUNK, IS_LINE_JUNK, Match, SequenceMatcher, context_diff, diff_bytes, get_close_matches, ndiff, restore, unified_diff)
   ```

## Module rewrites and behaviour differences

The bundled module follows CPython 3.12's `Lib/difflib.py`.  Its docstring lists
the rewrites needed by the compiler (a small `Match` class instead of
`namedtuple`, no `yield from`/f-strings/`str.format`, direct `_chain_b`, lists
instead of generator helpers, and the callable-wrapper shapes used by
`unified_diff`, `context_diff` and `IS_CHARACTER_JUNK`).  The behaviour
differences are: `diff_bytes` uses `latin-1` instead of ASCII +
`surrogateescape` and dispatches only to the bundled `unified_diff` /
`context_diff`; `IS_CHARACTER_JUNK` takes one argument (the programs never pass
the optional `ws`); `diff_bytes` does not accept an arbitrary `dfunc` value; and
`HtmlDiff`/`_mdiff` are not included.
