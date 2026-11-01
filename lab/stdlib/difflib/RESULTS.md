# `difflib` lab results

Twelve ordinary Python programs, each compiled with the default command
(`python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python`) and compared with
CPython 3.12's stdout and exit status.

The typed path refuses the `import difflib` in every program, so the default build falls
back to the general path.  Ten programs build there and match CPython; two are follow-ups.

| Program | Typed path | Default result | First refusal / note |
|---|---|---|---|
| `01_close_matches.py` | refused | general, matches | `import of 'difflib' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json)` |
| `02_config_typo.py` | refused | general, matches | same typed import refusal |
| `03_patch_preview.py` | refused | general, matches | same typed import refusal |
| `04_unified_edges.py` | refused | **refused** | see follow-up 1 |
| `05_context_patch.py` | refused | general, matches | same typed import refusal |
| `06_ndiff_restore.py` | refused | general, matches | same typed import refusal |
| `07_differ_junk.py` | refused | general, matches | same typed import refusal |
| `08_seq_ratio.py` | refused | general, matches | same typed import refusal |
| `09_seq_opcodes.py` | refused | general, matches | same typed import refusal |
| `10_seq_grouped.py` | refused | general, matches | same typed import refusal |
| `11_diff_bytes.py` | refused | general, matches | same typed import refusal |
| `12_htmldiff.py` | refused | **refused** | see follow-up 2 |

## What is built

The general-path prelude (`python/pkg-v12/prelude_genlib.py`, selected by
`python/pkg-v12/genlib.py`) now provides `get_close_matches`, `SequenceMatcher`,
`Differ`, `Match`, `unified_diff`, `context_diff`, `ndiff`, `restore`, `diff_bytes`,
`IS_LINE_JUNK` and `IS_CHARACTER_JUNK` with CPython 3.12's algorithms and output
formatting.  The one implementation choice is that `diff_bytes` uses `latin-1` instead
of CPython's ASCII + `surrogateescape`; for the byte strings in these programs the
decoded and re-encoded bytes are identical.

## Follow-ups (out of scope here)

1. `04_unified_edges.py`: a `**kwargs` call argument in the program (it forwards options
   to `unified_diff`) is not modelled by the general path.

   ```
   04_unified_edges.py:1:1: not in the subset: import of 'difflib' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: a **kwargs call argument
     write instead: drop the import and write what you need by hand with plain lists, dicts and loops
   ```

2. `12_htmldiff.py`: `HtmlDiff` (HTML table / full page generation) is not implemented.

   ```
   12_htmldiff.py:1:1: not in the subset: import of 'difflib' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: difflib.HtmlDiff (not yet published in NAMES_library.json)
     write instead: drop the import and write what you need by hand with plain lists, dicts and loops
   ```
