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
`_replace_charref`, `_named_ref`, `_invalid_charrefs`, `_invalid_codepoints`, `_charref_end`)
and `entities.py` (name2codepoint, codepoint2name, entitydefs, html5).

`html5` keeps **every CPython value exactly, including all 133 strings above U+FFFF**
(`𝔄 𝕓 𝕊 ℤ`, not `?`).  `html/__init__.py` holds those 133 as name/codepoint parallel lists and
builds them with `chr()`, so `html.unescape` stays on the typed path.  `entities.py` builds
each table with a small function that returns a dict literal, so the typed path keeps a
literal-key lookup, `keys()`, `len()` and membership typed and exact:

```
$ python3 -c "import html.entities; print(html.entities.html5['Afr;'], html.entities.html5['bopf;'])"
𝔄 𝕓
```

A program that has to use the 16-bit v2 runtime (for example `08_entities_tables.py`, which
reads a table with `.get()` outside a function) cannot hold those values.  It is refused at
compile time by name, in both builds:

```
AIL_CURRENT/stdlib/html/entities.py:798:5: not in the subset: a non-BMP string literal in the 16-bit v2 runtime
```

That is a loud, located refusal: no wrong character (`?`) and no run-time `chr_non_bmp` stop.

Measured with the default command and with `AIL_UNIFIED_FORCE=1` (`python3 -B` for the oracle):

| program | default build | `AIL_UNIFIED_FORCE=1` | CPython match |
|---|---|---|---|
| 01_escape_quote_true | typed | typed | yes / yes |
| 02_escape_quote_false | typed | typed | yes / yes |
| 03_escape_alias | typed | typed | yes / yes |
| 04_unescape_named | typed | typed | yes / yes |
| 05_unescape_numeric | typed | typed | yes / yes |
| 06_unescape_invalid | typed | typed | yes / yes |
| 07_unescape_plain | typed | typed | yes / yes |
| 08_entities_tables | refused (non-BMP, by name) | refused (non-BMP, by name) | refused by name |
| 09_entities_html5 | typed | refused (non-BMP, by name) | yes / refused by name |
| 10_strip_tags | typed | typed | yes / yes |
| 11_roundtrip | typed | typed | yes / yes |
| 12_mixed | typed | refused (non-BMP, by name) | yes / refused by name |

Default build: 11 of 12 build and match CPython (08 is refused by name).
Unified build: 9 of 12 build and match (08, 09 and 12 are refused by name because the table
module carries the astral literals the 16-bit runtime cannot hold).
The three escape-only programs are typed with no general-path note.

`html.unescape` of an astral named reference is exact on the typed path
(`&Afr;&bopf;&Sopf;&Zopf;` -> `'𝔄𝕓𝕊ℤ'`), and numeric astral references (`&#x1F600;`) match.
On the 16-bit general path an astral `chr()` stops with the named `chr_non_bmp` limit, the same
limit CPython-numeric astral references already hit there; it never returns a wrong character.
This is unchanged from the base compiler's `chr()`.

## Build time

`AIL_NO_CACHE=1`, on the 4-core runner.

| build | time |
|---|---|
| hello world (`print("hello")`), median of 3 | 0.21 s |
| program importing `html.entities.html5` (09_entities_html5), median of 3 | 14.6 s |
| program importing `html` only, typed (04_unescape_named) | 7.6 s |
| existing bundled module `shlex` (reference) | 7.1 s |

The 2231-entry table is now a dict literal built by a function rather than a compact string
parsed at import, so the compile cost is the generated C for the literal.  The task's target
(under 2 x hello world, 0.42 s) is still not met and cannot be met with this compiler: even
`import shlex` costs 7.1 s against 0.21 s for hello world, so the floor is the compiler's own
module pass, not the html package.

## Follow-up for `ail_modules.py`

Every build prints on stderr:

```
note: html/__init__.py shadows the standard library module html, as it does in CPython
```

It is informational and matches CPython (a package in `stdlib/` is intended to shadow), but
the wording suggests a true shadowing event. Worth quieting in `ail_modules.py`; not edited
here.

## Regression guard

Bundling `html` makes it a *local* module to the compiler, which changes the four guards that
encoded the old "`html` is not modelled" behaviour.  The guards were updated, not gutted:

- `test_ail_pre105` used `import math, html` as the unmodelled module; a bundled package makes
  that a local/std mix (`one 'import' statement mixes local modules and others`), so the guard
  now uses `xml` / `xml.etree` (still unmodelled).  The mixed-import rule itself is unchanged;
  this is a direct consequence of the task's "bundled package" requirement and cannot be
  avoided without not shipping `html` at all.
- `test_ail_pre52`: the guarded-import cases whose module now exists are decided at build time
  (the file already had a `DECIDED` list for that); `xml` is used for the plain mixed import
  and `math` for the handler/`else` cases, whose location check would otherwise pick up the
  informational shadow note.
- `test_ail_stdtop4`: `html.unescape` and `from html import *` now work, so they are no longer
  refusal cases; the bad-`html.escape` cases assert the messages the bundled `escape`
  definition produces.  `esc = html.escape` is now a named refusal ("using function
  html.escape as a first-class value (it has defaults...)"), because the typed path cannot pass
  a function with a default as a value; the guard keeps the aliasing form as that refusal.

All four guards pass:

```
python3 tools/par_check.py -j 2 test_ail_std_html test_ail_pre105 test_ail_pre27 test_ail_pre52 test_ail_stdtop4
```

## Test

`AIL_CURRENT/test_ail_std_html.py` builds each program in the default and unified builds,
compares stdout and exit status with `python3`, requires the named non-BMP refusal where the
table cannot be typed, asserts no general-path note for the escape-only programs, and checks
`html.entities.html5['Afr;']` / `['bopf;']` and `keys()` exactly.  Registered in
`AIL_CURRENT/tests.d/test_ail_std_html.txt`.
