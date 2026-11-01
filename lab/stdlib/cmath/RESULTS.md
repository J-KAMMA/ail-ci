# `cmath` coverage (job-std_cmath-11020039)

Environment: CPython 3.12.3, the default build `python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python`
(typed path first, general path as the fallback). Date: 2026-11-01.

The twelve programs are 15–60 lines each and use `cmath` the way ordinary code does: `sqrt`, `exp`, `log`,
`log` with a base, `log10`, `sin`/`cos`/`tan`, the hyperbolic and inverse functions, `phase`, `polar`, `rect`,
`isclose` (`rel_tol=`, `abs_tol=`), `isfinite`/`isnan`/`isinf`, the constants (`pi`, `e`, `tau`, `inf`, `nan`,
`infj`, `nanj`), complex literals and `complex(...)`, arithmetic on the results, branch cuts, signed zeros,
infinities and NaNs, empty inputs, and the `ValueError` / `OverflowError` cases caught by the program.

## Before the fixes

The module was not modelled at all: every program was refused, 0 of 12 built.

| program | result | first refusal message |
| --- | --- | --- |
| `branch_cuts.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: cmath.sqrt (not yet published in NAMES_library.json)` |
| `error_handling.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: the name 'complex' is not a known function/class/builtin` |
| `filter_response.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: the name 'complex' is not a known function/class/builtin` |
| `impedance.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: cmath.phase (not yet published in NAMES_library.json)` |
| `inverse_trig.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: cmath.asin (not yet published in NAMES_library.json)` |
| `log_transform.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: cmath.log10 (not yet published in NAMES_library.json)` |
| `mandelbrot.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: the name 'complex' is not a known function/class/builtin` |
| `phasors.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: cmath.rect (not yet published in NAMES_library.json)` |
| `quadratic.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: the name 'complex' is not a known function/class/builtin` |
| `rotation.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: cmath.polar (not yet published in NAMES_library.json)` |
| `trig_identities.py` | refused | `p.py:6:5: not in the subset: the result of check_sin_cos() is declared bool, but `cmath.isclose(left, complex(1.0, 0.0)...` is not a bool (Python would keep the number and print it as one); return a bool: True/False, a comparison, `not`, or `cmath.isclose(left, complex(1.0, 0.0)... != 0` (the general path could not build this program either); general path: cmath.sin (not yet published in NAMES_library.json)` |
| `wave_superposition.py` | refused | `p.py:1:1: not in the subset: import of 'cmath' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: cmath.exp (not yet published in NAMES_library.json)` |

## After the fixes

| program | result | CPython stdout + exit |
| --- | --- | --- |
| `branch_cuts.py` | general | match |
| `error_handling.py` | general | match |
| `filter_response.py` | general | match |
| `impedance.py` | general | match |
| `inverse_trig.py` | general | match |
| `log_transform.py` | general | match |
| `mandelbrot.py` | general | match |
| `phasors.py` | general | match |
| `quadratic.py` | general | match |
| `rotation.py` | general | match |
| `trig_identities.py` | general | match |
| `wave_superposition.py` | general | match |

After: 12 of 12 build and all 12 match CPython's stdout and exit code. The test
`AIL_CURRENT/test_ail_std_cmath.py` (registered by `tests.d/test_ail_std_cmath.txt`) compiles every program
in the default mode, runs it and compares both exit code and stdout with CPython.

## Self-check probes

Run from `/tmp/probes/` with `bash ~/tools/cmp.sh <probe>.py $PWD`, which builds both the forced general
path (`g`) and the default build (`d`) and compares each with CPython 3.12:

| probe | what it covers | result |
| --- | --- | --- |
| `pcm1.py` | the common calls, literals, constants and predicates | g, d match |
| `pforms.py` | `import cmath as`, `from cmath import`, aliases, complex literals, every `complex(...)` form, arithmetic, comparison, a value through an argument, a list item, an attribute and a dict value | g, d match |
| `pflow.py` | empty inputs, negative values, signed zeros, caught `ValueError`/`OverflowError`, constants | g, d match |
| `pnum.py` | about 220 finite values (including zeros, subnormals and `1e308`) through all 16 numerical functions | g, d match |
| `pspecial.py` | the special-value table: infinities, NaNs, signed zeros, `rect`/`polar`, overflow and domain errors, `isclose`/`isnan`/`isinf` | g, d match |
| `pstrings.py` | complex string parsing, good and malformed forms with CPython's `ValueError` text | g, d match |
| `phash.py`, `phash2.py` | `hash`, equality and dict lookup of complex values over finite, infinite and extreme values (NaN hashes are process-dependent in CPython too) | g, d match |

## What was fixed

* New `python/pkg-v12/cmathlib.py` (called from `stdlib5.py`) lowers `cmath` names and constants, complex
  literals (`1j`, `2+3j`) and `complex(...)` (positional, `real=` / `imag=`, string, int, float and complex
  arguments) onto the Python source of `python/pkg-v12/prelude_cmath.py`.
* `prelude_cmath.py` is a plain-Python class `_AilComplex` with the arithmetic operators, `abs`, comparison,
  hash and CPython's complex `repr`, plus the whole `cmath` function set. The numerical algorithms and the
  special-value tables are CPython 3.12's `Modules/cmathmodule.c` and `Objects/complexobject.c`, so the
  branch cuts, signed zeros, infinities, NaNs and last bits agree with CPython. The `ValueError` cases
  (`log(0)`, `atanh(±1)`, `exp`/`cosh`/`sinh`/`tan` of an infinite imaginary part, `rect` with an infinite
  angle) and the `OverflowError` cases (`exp`, `cosh`, `sinh`, `polar`) are raised at the same points.
* The rewrite runs only when the program imports `cmath` (or a name from it), so the generated C of the other
  lab/compare programs is unchanged.

The programs build on the general path because the complex class uses operator methods; the typed path
refuses them and the default build falls back, as it does for `fractions.Fraction`. There are no follow-ups:
no refusal in this set needs a new feature.
