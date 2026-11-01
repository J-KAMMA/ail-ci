# fractions: real-program coverage

Twelve programs in this directory use `fractions` the way ordinary code does: arithmetic
and comparisons, string/float/tuple construction, keyword arguments, `round`,
`limit_denominator`, `as_integer_ratio`, `is_integer`, sorting/hashing/dict keys, exceptions,
and a stdin filter. They are 15-60 lines each and are built with

    AIL_CURRENT/ail_chatgpt.py compile <file>.py --syntax python

## Result

All twelve build in the default mode and match CPython 3.12 stdout and exit code.
Every one is built on the **general** path: the typed path does not accept the dunder
methods in `prelude_fraction.py` (`Fraction.__float__`, `__eq__`, ...), so the default
build falls back to the general runtime and completes.

| # | program | result | CPython stdout + exit |
| --- | --- | --- | --- |
| 1 | `approximation.py` | general | match |
| 2 | `basic_arith.py` | general | match |
| 3 | `bill_split.py` | general | match |
| 4 | `collections_sort.py` | general | match |
| 5 | `keyword_forms.py` | general | match |
| 6 | `mixed_ops.py` | general | match |
| 7 | `music.py` | general | match |
| 8 | `parse_forms.py` | general | match |
| 9 | `probability.py` | general | match |
| 10 | `recipe.py` | general | match |
| 11 | `stats.py` | general | match |
| 12 | `unit_convert.py` | general | match (empty stdin and a mixed valid/invalid input) |

The first build after the programs were written had 11 built (2 of them with different
stdout) and 1 refused:

| program | first result | first message / difference |
| --- | --- | --- |
| `keyword_forms.py` | refused | `p.py:235:5: not in the subset: dunder method Fraction.__float__; only __init__ is supported here, no other dunder (__eq__, __repr__, __len__, __add__, ...) (the general path could not build this program either); general path: round() got an unexpected keyword argument 'ndigits'` |
| `bill_split.py` | general, stdout differed | CPython prints `ZeroDivisionError Fraction(1, 0)`; the general runtime printed `Fraction(200, 0)` |
| `probability.py` | general, stdout differed | CPython prints `KeyError (9, 9)`; the general runtime printed `KeyError '(9, 9)'` |

## Fixes

* `python/pkg-v12/prelude_fraction.py`: `_ail_fr_div` formatted the numerator (`da`) in the
  `ZeroDivisionError` message instead of the denominator (`db`), so `Fraction(200, 1) / 0`
  reported `Fraction(200, 0)` instead of CPython's `Fraction(1, 0)`.
* `python/pkg-v12/pyboxed2.py`: the general-path `round()` builtin now accepts the CPython
  keyword names `number` and `ndigits` in either order, so `round(f, ndigits=2)` and
  `round(number=f, ndigits=2)` build. A missing `number`, a duplicate argument and an unknown
  keyword are refused by name; only `ndigits=` alone used to be misread as the number.
* `python/pkg-v12/tuplegen.py`, `python/pkg-v12/tuplib.py`: a generated tuple-key dict table
  whose `KeyError` is caught now passes the key itself as `args[0]` instead of an already
  stringified key. `str(exc)` for a tuple key is now CPython's `(9, 9)`, not `'(9, 9)'`.
  The raw-key form is selected only when the program binds a `KeyError` handler, so programs
  without one keep their previous generated C.

## Follow-ups

None. No refusal needed a new feature after the three fixes above.
