# `math` real-program coverage

Date: 2026-11-01. Build command for every row:

```
AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/math/<name>.py --syntax python -o /tmp/<name>
```

`typed` means the default build stayed on the typed path, `general` means the default build fell back to
the general path (the compiler prints its fallback note on stderr), and `refused` means the default build
failed. Every built program was run and its stdout and exit code were compared with CPython 3.12.3; all
ten match. Each was also built with `AIL_UNIFIED_FORCE=1` (general path) and with the default build, and
both builds match CPython as well.

| program | default result | CPython stdout / exit |
| --- | --- | --- |
| `circle_pack.py` | typed | match / 0 |
| `compound_growth.py` | general | match / 0 |
| `distance_report.py` | general | match / 0 |
| `floating_edges.py` | general | match / 0 |
| `gamma_table.py` | refused | -- |
| `ieee_parts.py` | refused | -- |
| `normal_probability.py` | general | match / 0 |
| `number_theory.py` | general | match / 0 |
| `prime_report.py` | general | match / 0 |
| `projectile.py` | general | match / 0 |
| `statistics_summary.py` | general | match / 0 |
| `wave_samples.py` | general | match / 0 |

Result: **10 of 12 build**, all ten print CPython's stdout and exit code.

## What was fixed

The twelve programs were written first. Their common calls named four missing pieces, and each piece
blocked at least one program (verified with the probes listed at the end):

* `math.prod(iterable, start=...)`: the keyword form and a start value, including `math.prod([],
  start=1)`. The helper now takes the start value and the lowering accepts only the `start=` keyword
  (`math.prod` takes one positional argument in CPython).
* `math.dist(p, q)`: two sequences, CPython's same-length `ValueError`, and its scaled norm so huge
  values do not overflow while `inf` / `nan` flow through as CPython's do.
* `math.erf(x)` / `math.erfc(x)`: the two C libm calls, with CPython's `inf` / `nan` results.
* `math.nextafter(x, y)` / `math.remainder(x, y)`: the C libm calls, with `remainder`'s
  `ValueError("math domain error")` for a zero divisor and an infinite operand.

`math.fsum` and the previous `math.prod` calls are unchanged in result: the new start value defaults to
`1`, so the old programs' stdout is the same.

## Refusals (out of scope here)

`gamma_table.py` fails at its first `math.gamma` use:

```
lab/stdlib/math/gamma_table.py:4:5: not in the subset: math.gamma() with these arguments is not built (see the note below) (the general path could not build this program either); general path: math.gamma (not yet published in NAMES_library.json)
note: lab/stdlib/math/gamma_table.py:4: math.gamma() with these arguments is not built; the math names built here are ...
```

Follow-up: `math.gamma` / `math.lgamma` need CPython's libm wrappers plus its domain / pole / overflow
error table (`gamma(0)` is `ValueError`, `gamma(200)` is `OverflowError`, `lgamma(0)` is
`ValueError`). The program was not changed to avoid them.

`ieee_parts.py` fails at its first `math.frexp` use:

```
lab/stdlib/math/ieee_parts.py:4:5: not in the subset: tuple assignment from Call; the right-hand side has to be a literal tuple of the same length, or a NAME already bound to a row -- bind it first (r = ...) and unpack the name (the general path could not build this program either); general path: math.frexp (not yet published in NAMES_library.json)
note: lab/stdlib/math/ieee_parts.py:4: math.frexp() with these arguments is not built; the math names built here are ...
```

Follow-up: `math.frexp` returns a two-item result (the tuple-arm of the result is a separate feature),
`math.ldexp` needs the integer exponent call, and `math.ulp` needs the spacing computation. The program
was not changed to avoid them.

## Checks

* `test_ail_std_math.py` builds the ten passing programs in the default mode and compares stdout and the
  exit code with CPython; `AIL_CURRENT/tests.d/test_ail_std_math.txt` registers it.
* Probes in `/tmp/probes/math/` and `/tmp/probes/feat/` cover `prod` with empty, negative, float and
  non-default start values; `dist` with empty, unequal, negative, huge, `inf`, `nan`, int and float
  points; `erf` / `erfc` at both infinities, `nan`, negative zero and values through an argument, a list
  item, an attribute and a dict value; `nextafter` / `remainder` at zero, signed zero, `inf`, `nan`, a
  zero divisor and the same four value paths. Each probe matches CPython on both `cmp.sh` builds.
* `lab/stdlib/math` programs were not changed to avoid a missing math name; the two refused programs stay
  written the way typical code would use them.
