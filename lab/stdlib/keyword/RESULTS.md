# `keyword` and `token` coverage results

Both modules ship as AIL source in `AIL_CURRENT/stdlib/`, beside `getopt.py` and `shlex.py`. A
program that says `import keyword` or `import token` finds them after its own directory and
`AIL_PATH` (`ail_modules.py`, `BUNDLED_DIR`).

Build command for every program, in both modes (the second sets `AIL_UNIFIED_FORCE=1`):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/<module>/<program>.py -o <out>
```

The oracle is `python3 <program>.py` (CPython 3.12.3). Every program is compared by stdout and
exit code on the default build and on `AIL_UNIFIED_FORCE=1`; all twelve agree on both, and every
program that mentions `keyword` is typed on the default build (no `note: ... built on the general
path ...`).

## Before

Measured at the base commit with no bundled `keyword.py` / `token.py`, on the sources committed
here.

`keyword` was already partly modelled by the compiler's batch-5 library pass (`smalllib5.py`
rewrites `kwlist`, `softkwlist` and direct `iskeyword(...)` / `issoftkeyword(...)` calls).
`keyword` used as a value (`filter(keyword.iskeyword, words)`) was refused, and every `token`
program was refused at the import. The common first-refusal prefix `P` follows (the per-module
`general path:` tail names the first use):

```
not in the subset: import of '<module>' is not available: this compiler builds only the modules
it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general
path could not build this program either); general path:
```

| program | default build | first refusal or fallback | CPython stdout + exit |
| --- | --- | --- | --- |
| `keyword/01_kwlist.py` | typed | — | same, exit 0 |
| `keyword/02_soft_keywords.py` | typed | — | same, exit 0 |
| `keyword/03_iskeyword.py` | typed | — | same, exit 0 |
| `keyword/04_value_passing.py` | refused | `P keyword.iskeyword (not yet published in NAMES_library.json)` | same, exit 0 |
| `keyword/05_identifier_checker.py` | typed | — | same, exit 0 |
| `keyword/06_keyword_table.py` | typed | — | same, exit 0 |
| `token/07_token_constants.py` | refused | `P token.ENDMARKER used as a plain value` | same, exit 0 |
| `token/08_tok_name.py` | refused | `P token.tok_name used as a plain value` | same, exit 0 |
| `token/09_exact_token_types.py` | refused | `P token.EXACT_TOKEN_TYPES used as a plain value` | same, exit 0 |
| `token/10_terminal_predicates.py` | refused | `P token.ENDMARKER used as a plain value` | same, exit 0 |
| `token/11_token_lookup.py` | refused | `P token.tok_name used as a plain value` | same, exit 0 |
| `token/12_token_table.py` | refused | `P token.N_TOKENS used as a plain value` | same, exit 0 |

Result before: **5 built (5 typed, 0 general), 7 refused**.

## After

### The modules

`AIL_CURRENT/stdlib/keyword.py` is CPython 3.12's `Lib/keyword.py`. Only what the compiler refuses
is rewritten: `iskeyword` and `issoftkeyword` are `def`s over a set instead of
`frozenset(...).__contains__` (the census's `field '__contains__' requires a class instance`).
`__all__`, `kwlist` and `softkwlist` keep CPython's values.

`AIL_CURRENT/stdlib/token.py` is CPython 3.12's `Lib/token.py`. `tok_name` and the names its
`__all__` extension carried are written out as one dict literal and one list literal (CPython
builds them from `globals()`); `ISEOF` compares with the literal `0` (the default build reads the
bare name `ENDMARKER` in that one return as the string in `tok_name`, though it reads the same
name correctly everywhere else). Every constant, `tok_name` (70 entries), `EXACT_TOKEN_TYPES` (48
entries) and the three predicates keep CPython's values; the docstring shows how to regenerate the
two tables.

| program | default build | `AIL_UNIFIED_FORCE=1` | stdout + exit vs CPython |
| --- | --- | --- | --- |
| `keyword/01_kwlist.py` | typed | typed | same, exit 0 |
| `keyword/02_soft_keywords.py` | typed | typed | same, exit 0 |
| `keyword/03_iskeyword.py` | typed | typed | same, exit 0 |
| `keyword/04_value_passing.py` | typed | typed | same, exit 0 |
| `keyword/05_identifier_checker.py` | typed | typed | same, exit 0 |
| `keyword/06_keyword_table.py` | typed | typed | same, exit 0 |
| `token/07_token_constants.py` | typed | typed | same, exit 0 |
| `token/08_tok_name.py` | typed | typed | same, exit 0 |
| `token/09_exact_token_types.py` | typed | typed | same, exit 0 |
| `token/10_terminal_predicates.py` | general | typed | same, exit 0 |
| `token/11_token_lookup.py` | typed | typed | same, exit 0 |
| `token/12_token_table.py` | typed | typed | same, exit 0 |

Result after: **12 built, 11 typed, 1 general, 0 refused**; every `keyword` program is typed.
The test `AIL_CURRENT/test_ail_std_keyword.py` builds all twelve in both modes and compares
stdout and exit status with `python3`.

## Follow-ups (need a compiler file)

1. `keyword/04_value_passing.py` works because the bundled module is loaded when the batch-5
   rewrite sees `filter(keyword.iskeyword, ...)`. A program whose only use is
   `keyword.iskeyword` as a value still falls back; the bundled file covers it.
2. `token/10_terminal_predicates.py` is general on the default build, though it builds and matches
   on both paths. Any use of `token.ISEOF(...)` produces:

   ```
   AIL_CURRENT/stdlib/token.py:106:1: built on the general path (about 20x slower) because a
   str constant 'ENDMARKER' used where a number is needed
   ```

   (`smalllib5.py`/`pyfunc.py` constant folding: the module's int-to-str `tok_name` literal is
   read as a list of numbers when a function in the same module is called). `--strict` still
   builds the program. This is the only non-typed program.
3. `str.isidentifier()` is not built on the typed path (`isidentifier() and isprintable() are not
   built`), so `keyword/05_identifier_checker.py` spells the identifier test with
   `isalpha`/`isdigit`/`_`; CPython's `.isidentifier()` is otherwise the natural spelling.
