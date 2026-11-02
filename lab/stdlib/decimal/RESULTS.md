# `decimal` lab: results

Built with the default command (`python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python -o exe`)
on 2026-11-01, then run with the same empty stdin as CPython 3.12.  A build whose stderr starts with
`note: ... built on the general path` is reported as **general**; **typed** is a build with no fallback
note; **refused** is a non-zero build, with its first refusal line.

| program | initial build | final build | first refusal / general-path reason |
| --- | --- | --- | --- |
| `basic_arith.py` | general | general | showing a computed Decimal that may be None; bind it to a name first |
| `construction.py` | general | general | parameter `bn` of `_dec_cmp_parts()` is declared bool, but `bn` is not a bool |
| `context_precision.py` | general | general | showing a computed Decimal that may be None; bind it to a name first |
| `digit_inspector.py` | refused | general | `not in the subset: decimal.Decimal.as_tuple is not supported (see the note below)` |
| `division_mod.py` | general | general | showing a computed Decimal that may be None; bind it to a name first |
| `edge_errors.py` | general | general | showing a computed Decimal that may be None; bind it to a name first |
| `formatting.py` | general | general | a format spec on a Decimal in an f-string (`__format__` is not built) |
| `invoice_totals.py` | general | general | a format spec on a Decimal in an f-string (`__format__` is not built) |
| `powers_sqrt.py` | general | general | showing a computed Decimal that may be None; bind it to a name first |
| `quantize_round.py` | general | general | showing a computed Decimal that may be None; bind it to a name first |
| `rounding_modes.py` | general | general | showing a computed Decimal that may be None; bind it to a name first |
| `scientific_parse.py` | general | general | showing a computed Decimal that may be None; bind it to a name first |

Final: **12 / 12 build**, all on the general path, and all match CPython 3.12 stdout and exit status.
`test_ail_std_decimal.py` compares the 12 programs with CPython; the probes in `/tmp/probes` cover
`as_tuple` values, large coefficients, construction from floats, error paths, aliasing and values reaching
the prelude through an argument, a list item, an attribute and a dict value on both builds.

## Fixed

- `Decimal.as_tuple` was refused by name.  It is now built, including the empty digit tuple of a NaN,
  `"F"` for infinity, `"n"` / `"N"` for quiet / signalling NaN, and a `DecimalTuple`-shaped result with
  `.sign`, `.digits`, `.exponent`, `_fields`, tuple indexing, slicing, iteration, unpacking, containment,
  `count` / `index`, concatenation, hashing and CPython's `DecimalTuple(...)` repr.
- `Decimal(d.as_tuple())` round-trips: `Decimal.__init__` accepts the `_DecTuple` result directly (and
  still accepts a plain tuple or list), and `reversed(d.as_tuple())` returns the fields reversed.  Like
  the namedtuple prelude, `_DecTuple` is a class rather than a tuple subclass, so
  `isinstance(d.as_tuple(), tuple)` is `False`; the tuple protocol and the three fields are emulated.
- The int64 default keeps Decimal coefficients arbitrary precision (a `_DecInt` coefficient in
  `prelude_decimal.py`) while the program's own ints stay int64; construction from a float, arithmetic,
  quantize, sqrt, format and `as_tuple` therefore work for coefficients wider than 64 bits.  A coefficient
  that fits in int64 now keeps its native value and uses the int64 fast paths, promoting to the string
  algorithms exactly when the operation would overflow, so ordinary arithmetic does not pay the
  arbitrary-precision cost.  An int returned to the program still follows the normal int64 rule and stops
  loudly rather than wrapping.

## Follow-up

No follow-up is required for these 12 programs.  The prelude still names these larger, unbuilt features
(not used by the lab programs), with the exact first refusal text from `/tmp/probes`:

- `Decimal.ln`: `not in the subset: decimal.Decimal.ln is not supported (see the note below)`
- context traps: `not in the subset: decimal.Context.traps is not supported (see the note below)`

`exp`, `log10`, `logb`, `fma`, `scaleb`, `rotate`, `shift`, the `logical_*` / `next_*` methods,
`BasicContext` / `ExtendedContext` / `DefaultContext`, three-argument `pow` and a non-integer exponent
remain refused by name for the same reason: the libmpdec transcendental / context machinery is not
rebuilt.
