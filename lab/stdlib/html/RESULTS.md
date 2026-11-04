# html2: `html.unescape` and `html.entities` as a bundled AIL package

Programs: `lab/stdlib/html/01..12`. Oracle: CPython 3.12 (`python3 -B`), stdout and exit status.
Baseline branch: `integ` at `c5eb37762b37`.

## Before (integ c5eb37762b37)

The bundled package is the only change, so the baseline was measured with
`AIL_CURRENT/stdlib/html/` moved aside: the compiler's own `html.escape` model applies and
`html.unescape` / `html.entities` are unavailable.

| program | result | first refusal |
|---|---|---|
| 01_escape_quote_true | typed, matches | |
| 02_escape_quote_false | typed, matches | |
| 03_escape_alias | general path, matches | |
| 04_unescape_named | refused | `04_unescape_named.py:10:5: not in the subset: html.unescape is not supported` |
| 05_unescape_numeric | refused | `05_unescape_numeric.py:10:5: not in the subset: html.unescape is not supported` |
| 06_unescape_invalid | refused | `06_unescape_invalid.py:11:5: not in the subset: html.unescape is not supported` |
| 07_unescape_plain | refused | `07_unescape_plain.py:18:5: not in the subset: html.unescape is not supported` |
| 08_entities_tables | refused | `08_entities_tables.py:3:1: not in the subset: E.name2codepoint used as a plain value` |
| 09_entities_html5 | refused | `09_entities_html5.py:9:5: not in the subset: E.html5 used as a plain value` |
| 10_strip_tags | refused | `10_strip_tags.py:17:5: not in the subset: html.unescape is not supported` |
| 11_roundtrip | refused | `11_roundtrip.py:14:5: not in the subset: html.unescape is not supported` |
| 12_mixed | refused | `12_mixed.py:5:1: not in the subset: html.unescape is not supported` |

3 of 12 build (2 typed), 9 refused.

Guard tests before the change: all four pass (`test_ail_pre105`, `test_ail_pre27`,
`test_ail_pre52`, `test_ail_stdtop4`).

## After

`AIL_CURRENT/stdlib/html/` is a bundled package: `__init__.py` (escape, unescape,
`_replace_charref`, `_invalid_charrefs`, `_invalid_codepoints`, `_charref_end`) and
`entities.py` (name2codepoint, codepoint2name, entitydefs, html5).

| program | default build | `AIL_UNIFIED_FORCE=1` | CPython match |
|---|---|---|---|
| 01_escape_quote_true | typed | typed (spot-checked) | yes |
| 02_escape_quote_false | typed | not re-run | yes |
| 03_escape_alias | typed | not re-run | yes |
| 04_unescape_named | typed | typed (spot-checked) | yes |
| 05_unescape_numeric | typed | not re-run | yes |
| 06_unescape_invalid | typed | not re-run | yes |
| 07_unescape_plain | typed | not re-run | yes |
| 08_entities_tables | general path | not re-run | yes |
| 09_entities_html5 | general path | not re-run | yes |
| 10_strip_tags | typed | typed (spot-checked) | yes |
| 11_roundtrip | typed | not re-run | yes |
| 12_mixed | general path | not re-run | yes |

Only 01, 04 and 10 were re-built with `AIL_UNIFIED_FORCE=1` (all typed, all matching); the rest
were verified in the default build only.

11 of 12 build and match CPython; the three escape-only programs are typed with no
general-path note (all three were checked in the default build; 01 in both). General-path note for the entities programs:

```
html/entities.py:265:1: built on the general path ... because a str constant 'AElig' used
where a number is needed
```

This is the compiler's int-keyed-dict limitation (`codepoint2name` is int -> str), not an html
issue; the programs remain correct. Making those tables hash maps on the typed path is a
follow-up in the compiler, not in this package.

## Build time

`AIL_NO_CACHE=1`, single build each (median not taken: a 3-run median of the 260 s case does
not fit the job budget).

| build | time |
|---|---|
| hello world (`print("hello")`), median of 3 | 0.21 s |
| program importing `html.entities.html5` (09_entities_html5, general path) | 260.4 s |
| program importing `html` only, typed (04_unescape_named) | 13.2 s |
| existing bundled module `shlex` (reference, compiler-only phase 2.3 s) | 9.3 s |

Target was under 2 x hello world (0.42 s); **not met**. The floor is the compiler itself: its
Python phase is 0.16 s for hello world but 2.3 s for any bundled module, and the 2231-entry
dict literal is emitted as one C statement that `cc -O2` takes 6.3 s on. Even `shlex` is 44x
hello world, so the target is unreachable without a compiler change (a compact string table
would cut the C size but not the 2.3 s merge/inference floor).

## Follow-up for `ail_modules.py`

Every build prints on stderr:

```
note: html/__init__.py shadows the standard library module html, as it does in CPython
```

It is informational and matches CPython (a package in `stdlib/` is intended to shadow), but
the wording suggests a true shadowing event. Worth quieting in `ail_modules.py`; not edited
here.

## Regression guard — STOP CONDITION HIT

`python3 tools/par_check.py -j 2 test_ail_pre105 test_ail_pre27 test_ail_pre52 test_ail_stdtop4`

- `test_ail_pre27`, `test_ail_pre52`, `test_ail_stdtop4`: pass (no failures reported).
- `test_ail_pre105`: **fails, 17 subtests** in
  `test_refusal_names_the_unmodelled_module_only`.  That test requires `import math, html`
  (with `html` used) to be refused because `html` is unmodelled.  A bundled `html` package
  makes the import succeed / changes the refusal, so the test's premise no longer holds.
  Exact message:

```
FAIL: test_refusal_names_the_unmodelled_module_only (...) (name='attribute', general=False)
AssertionError: 'html' not found in 'prog.py:1:1: one `import` statement mixes local modules
and others; the compiler needs them apart.\n  write instead: one `import` line for the local modules
```

and for `dotted`:

```
AssertionError: "import of 'html.parser'" not found in "prog.py:1:1: no module named
'html.parser': the search path (...) has no such file or directory."
```

This cannot be fixed inside the package: any package named `html` on the bundled search path
makes `html` available, which is the opposite of what `test_ail_pre105` asserts.  It needs a
change to that test (or to the compiler's notion of a modelled module), both outside the files
this job may edit.  The bundled package was left in place; the job stopped here per the stop
rule.

## Test

`AIL_CURRENT/test_ail_std_html.py` builds every program in both builds, compares stdout and
exit status with `python3`, and asserts no general-path note for the escape-only programs.
Registered in `AIL_CURRENT/tests.d/test_ail_std_html.txt`.
