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

Measured with the base compiler (no bundled `keyword.py` / `token.py`) on the sources committed
here.

`keyword` was already partly modelled by the compiler's batch-5 library pass (`smalllib5.py`
rewrites `kwlist`, `softkwlist` and direct `iskeyword(...)` / `issoftkeyword(...)` calls), so all
six `keyword` programs already built typed. Every `token` program was refused at the import. The
common first-refusal prefix `P` follows (the per-program position is always `file:1:1`):

```
not in the subset: import of 'token' is not available: this compiler builds only the modules
it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general
path could not build this program either)
```

| program | default build | first refusal or fallback | CPython stdout + exit |
| --- | --- | --- | --- |
| `keyword/01_kwlist.py` | typed | — | same, exit 0 |
| `keyword/02_soft_keywords.py` | typed | — | same, exit 0 |
| `keyword/03_iskeyword.py` | typed | — | same, exit 0 |
| `keyword/04_value_passing.py` | typed | — | same, exit 0 |
| `keyword/05_identifier_checker.py` | typed | — | same, exit 0 |
| `keyword/06_keyword_table.py` | typed | — | same, exit 0 |
| `token/07_token_constants.py` | refused | `P` | same, exit 0 |
| `token/08_tok_name.py` | refused | `P` | same, exit 0 |
| `token/09_exact_token_types.py` | refused | `P` | same, exit 0 |
| `token/10_terminal_predicates.py` | refused | `P` | same, exit 0 |
| `token/11_token_lookup.py` | refused | `P` | same, exit 0 |
| `token/12_token_table.py` | refused | `P` | same, exit 0 |

Result before: **6 built (6 typed, 0 general), 6 refused**.

An earlier version of `04_value_passing.py` passed `keyword.iskeyword` straight to `filter`; at
base that was refused with `keyword.iskeyword (not yet published in NAMES_library.json)`. That
use cannot be typed correctly (see the saved-reference probe below), so the program now keeps
`keyword.iskeyword` calls direct and passes a program predicate to `filter` instead. The bare
value form is covered by the probe.

## After

### The modules

`AIL_CURRENT/stdlib/keyword.py` is CPython 3.12's `Lib/keyword.py`. `kwlist`, `softkwlist`,
`__all__` and the two predicates' names and results are CPython's. CPython writes
`iskeyword = frozenset(kwlist).__contains__`; the typed path has no value for a bound method of a
builtin, so the predicates are `def`s over a set marked `@lru_cache`:

* a call spelled `keyword.iskeyword(s)` is still typed;
* taking one as a first-class value (`f = keyword.iskeyword`) is a **named typed-path refusal**
  ("functools cache: keyword.iskeyword is used as a value; call it by name"), and the program is
  built on the general path, where the value is a real callable and prints `True`/`False`.

A plain `def` would instead be a typed function value whose `bool` result is printed as `1`/`0`
through the saved reference (`print(f("if"))` -> `1` where CPython says `True`) -- a silent
mismatch. The `@lru_cache` marker turns that into a fallback to the path that gets it right.

`AIL_CURRENT/stdlib/token.py` is CPython 3.12's `Lib/token.py`. `tok_name` and the names its
`__all__` extension carried are written out as one dict literal and one list literal (CPython
builds them from `globals()`). Every constant, `tok_name` (70 entries), `EXACT_TOKEN_TYPES` (48
entries) and the three predicates keep CPython's values and bodies, including
`ISEOF(x) = (x == ENDMARKER)`; the docstring shows how to regenerate the two tables.

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
stdout and exit status with `python3`; it also runs the two probes below.

### Probes for the typed-path limits

1. A saved predicate reference (refused at base, now built on the general path):

   ```python
   import keyword
   def main() -> None:
       f = keyword.iskeyword
       print(f("if"))
   main()
   ```

   CPython prints `True`. With the bundled file the default build prints `True` after a
   general-path fallback whose note names the value use; `AIL_UNIFIED_FORCE=1` prints `True`.
   `issoftkeyword` behaves the same. This is `test_saved_reference_falls_back`.

2. `token.ISEOF` reads the module's `ENDMARKER`, which a program may rebind:

   ```python
   import token
   def main() -> None:
       token.ENDMARKER = 5
       print(token.ENDMARKER, token.ISEOF(5), token.ISEOF(0))
   main()
   ```

   Both builds print `5 True False`, as CPython does. This is `test_iseof_reads_endmarker`.

## Follow-ups (need a compiler file)

1. `keyword.iskeyword`/`issoftkeyword` as a **typed** first-class value would let the saved
   reference stay on the typed path and print `True`/`False`. Today the general path runs it
   (the compiler's bool-returning-through-a-saved-reference bug prints `1`/`0` otherwise). The
   `@lru_cache` marker exists only to make that a loud, named fallback.
2. `token/10_terminal_predicates.py` is general on the default build, though it builds and matches
   on both paths. Any use of `token.ISEOF(...)` produces:

   ```
   AIL_CURRENT/stdlib/token.py:107:1: built on the general path (about 20x slower) because a
   str constant 'ENDMARKER' used where a number is needed
   ```

   (`smalllib5.py`/`pyfunc.py` constant folding: the module's int-to-str `tok_name` literal is
   read as a list of numbers when a function in the same module is called). `--strict` still
   builds the program. This is the only non-typed program.
3. `str.isidentifier()` is not built on the typed path (`isidentifier() and isprintable() are not
   built`), so `keyword/05_identifier_checker.py` spells the identifier test with
   `isalpha`/`isdigit`/`_`; CPython's `.isidentifier()` is otherwise the natural spelling.
