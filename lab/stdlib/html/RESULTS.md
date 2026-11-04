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

`entities.py` stores CPython's four tables compactly and rebuilds them at import, so it holds
**no non-BMP string constant** and compiles in the 16-bit v2 runtime.  `html5` is a read-only
mapping whose BMP values are exact and whose 133 values above U+FFFF are built with `chr()`
only when such a name is looked up.  `len()`, `in`, subscripting, `keys()`, `values()`,
`items()` and `get()` all work, and the key order is CPython's:

```
$ python3 -c "import html.entities as e; print(list(e.html5.keys())[:2], len(e.html5))"
['Aacute', 'aacute'] 2231
```

An astral lookup cannot be represented on the 16-bit runtime, so it stops with the named limit
`AIL limit: chr_non_bmp` (the same limit the compiler's own `chr()` already has there) instead
of returning a wrong character.  This is the price of keeping the whole table usable for every
BMP lookup in the 16-bit build: an unconditional non-BMP literal would instead refuse the
module at compile time and make even `html5['amp;']` unbuildable there.

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
| 08_entities_tables | general path, matches | general path, matches | yes / yes |
| 09_entities_html5 | general path, matches | general path, matches | yes / yes |
| 10_strip_tags | typed | typed | yes / yes |
| 11_roundtrip | typed | typed | yes / yes |
| 12_mixed | general path, matches | general path, matches | yes / yes |

Default build: 12 of 12 build and match CPython.  Unified build: 12 of 12 build and match.
The three escape-only programs are typed with no general-path note.  The programs that import
`html.entities` take the general path because the module's `html5.get` has an optional
`default` (the typed path requires plain positional parameters), but their output is exact.

`html.unescape` of an astral named reference is exact on the typed path
(`&Afr;&bopf;&Sopf;&Zopf;` -> `'𝔄𝕓𝕊ℤ'`), and numeric astral references (`&#x1F600;`) match.
On the 16-bit general path an astral `chr()` stops with the named `chr_non_bmp` limit, the same
limit CPython-numeric astral references already hit there; it never returns a wrong character.
This is unchanged from the base compiler's `chr()`.

## Build time

`AIL_NO_CACHE=1`, on the 4-core runner, median of 3.

| build | time |
|---|---|
| hello world (`print("hello")`), median of 3 | 0.18 s |
| program importing `html.entities.html5` (09_entities_html5), median of 3 | 61.9 s |

The target (under 2 x hello world, 0.36 s) is not met.  The compact tables cost far less than a
dict literal, but any program that imports `html.entities` still pays the module pass; even the
existing `import shlex` bundled module costs about 7 s against 0.18 s for hello world, so the
floor here is the compiler's module pass, not the html package.  The astral-free encoding is
what keeps the proportional cost down; the absolute target is out of reach for a bundled module
in this compiler.

## Follow-up for `ail_modules.py`

Every build prints on stderr:

```
note: html/__init__.py shadows the standard library module html, as it does in CPython
```

It is informational and matches CPython (a package in `stdlib/` is intended to shadow), but the
wording suggests a true shadowing event.  Worth quieting in `ail_modules.py`; not edited here.

## Regression guard

Bundling `html` makes it a *local* module to the compiler, which changes what the four guards
that encoded the old "`html` is not modelled" behaviour can assert.  They were updated, not
gutted (all four pass; see the command below):

- `test_ail_pre105` used `import math, html` as the unmodelled module; a bundled package makes
  that a local/std mix (`one 'import' statement mixes local modules and others`), so the guard
  now uses `xml` / `xml.etree` (still unmodelled).  The mixed-import rule itself is unchanged;
  this is a direct consequence of the task's "bundled package" requirement and cannot be
  avoided without not shipping `html` at all.
- `test_ail_pre52`: the guarded-import cases whose module now exists are decided at build time
  (the file already had a `DECIDED` list for that); `xml` is used for the plain mixed import and
  `math` for the handler/`else` cases.
- `test_ail_stdtop4`: `html.unescape` and `from html import *` now work, so they are no longer
  refusal cases; the bad-`html.escape` cases assert the messages the bundled `escape` definition
  produces, and the alias case is kept as a named refusal (`esc = html.escape`).

All four guards pass:

```
python3 tools/par_check.py -j 2 test_ail_std_html test_ail_pre105 test_ail_pre27 test_ail_pre52 test_ail_stdtop4
```

## Test

`AIL_CURRENT/test_ail_std_html.py` builds each program in the default and unified builds,
compares stdout and exit status with `python3`, asserts 12/12 in both, checks that the escape-
only programs are typed, checks `html.entities.html5.keys()[:2]`, `len()` and BMP values
exactly, and checks that an astral lookup stops with `chr_non_bmp` (never a wrong character).
Registered in `AIL_CURRENT/tests.d/test_ail_std_html.txt`.
