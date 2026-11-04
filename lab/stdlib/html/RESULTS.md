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
returns `chr(codepoint)`, so the module has no non-BMP string constant and keeps the typed
path.  A pure-Python fuzz of `unescape` against `html.unescape` (200k random strings plus every
named reference) reports 0 mismatches, and all four tables plus `_invalid_charrefs` /
`_invalid_codepoints` compare equal to CPython's.

`entities.py` keeps the 133 values as CPython literals.  Its int-keyed tables force it onto the
16-bit general runtime, which refuses a non-BMP constant by name instead of returning a wrong
character.

| program | default build | `AIL_UNIFIED_FORCE=1` | CPython match |
|---|---|---|---|
| 01_escape_quote_true | typed | typed | yes |
| 02_escape_quote_false | typed | typed | yes |
| 03_escape_alias | typed | typed | yes |
| 04_unescape_named | typed | typed | yes |
| 05_unescape_numeric | typed | typed | yes |
| 06_unescape_invalid | typed | typed | yes |
| 07_unescape_plain | typed | typed | yes |
| 08_entities_tables | refused (non-BMP) | refused (non-BMP) | refused by name |
| 09_entities_html5 | refused (non-BMP) | refused (non-BMP) | refused by name |
| 10_strip_tags | typed | typed | yes |
| 11_roundtrip | typed | typed | yes |
| 12_mixed | refused (non-BMP) | refused (non-BMP) | refused by name |

9 of 12 build and match CPython in both builds; the three escape-only programs are typed with
no general-path note.  The other three refuse the non-BMP table by name rather than silently
corrupting it.  Exact refusal line for 08/09/12 (both builds):

```
AIL_CURRENT/stdlib/html/entities.py:778:1: not in the subset: a non-BMP string literal in the 16-bit v2 runtime
```

`html.unescape` of an astral named reference is exact on the typed path
(`&Afr;&bopf;&Sopf;&Zopf;` -> `'𝔄𝕓𝕊ℤ'`).  On the 16-bit general path it stops with
`AIL limit: chr_non_bmp`, the same named limit CPython-numeric astral references already hit
there; it never returns a wrong character.

## Build time

`AIL_NO_CACHE=1`, on the 4-core runner.

| build | time |
|---|---|
| hello world (`print("hello")`), median of 3 | 0.17 s |
| program importing `html.entities.html5` (09_entities_html5) | 9.7 s, then **refused by name** (was 260.4 s building a `'?'` table) |
| program importing `html` only, typed (04_unescape_named) | 7.6 s |
| existing bundled module `shlex` (reference) | 7.1 s |

The 260 s C build of the 2231-entry literal is gone, but the task's target (under 2 x hello
world, 0.42 s) is still not met, and cannot be met with this compiler: a *refused* table import
still costs 9.7 s, and even `import shlex` costs 7.1 s against 0.17 s for hello world.  The
floor is the compiler's own module pass, not the html package.

## Follow-up for `ail_modules.py`

Every build prints on stderr:

```
note: html/__init__.py shadows the standard library module html, as it does in CPython
```

It is informational and matches CPython (a package in `stdlib/` is intended to shadow), but
the wording suggests a true shadowing event. Worth quieting in `ail_modules.py`; not edited
here.

## Regression guard

Bundling `html` makes it a *local* module to the compiler, which changes three guards that
encoded the old unmodelled-`html` behaviour.  Each edit keeps the guard's intent and only
replaces the now-modelled example:

- `test_ail_pre105` used `import math, html` as the unmodelled module; it now uses
  `xml` / `xml.etree` (still unmodelled stdlib).
- `test_ail_pre52`: `import math, html` (html unused) is a mixed local/std import now, so
  `plain_two_unused` uses `xml`; the two cases that import only inside a handler/`else` use
  `math`, so the informational shadow note no longer breaks their `startswith` location check.
- `test_ail_stdtop4`: `html.unescape` and `from html import *` are supported now, so those
  refusal cases are gone; the bad-`html.escape` cases assert the messages the bundled
  `escape` definition produces; the compiled program calls `html.escape` directly instead
  of aliasing it (a first-class package function with a default is refused on the general
  path, the same as any other bundled function).

All four guards pass:

```
python3 tools/par_check.py -j 2 test_ail_pre105 test_ail_pre27 test_ail_pre52 test_ail_stdtop4
```

## Test

`AIL_CURRENT/test_ail_std_html.py` builds every program in both builds, compares stdout and
exit status with `python3`, requires the non-BMP refusal for the entities programs, and
asserts no general-path note for the escape-only programs.  Registered in
`AIL_CURRENT/tests.d/test_ail_std_html.txt`.
