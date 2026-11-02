# prog21: typed reach of eight real programs (2026-11-02)

CPython 3.12.3.  Each program was run under `cProfile` with the same input repeated so the short
programs' own functions are measurable (1,000 repetitions; `t419` 300).  The rows below are every
function defined by the program, in own-time order, until the hot set holds 80% of the program's
own-function time.  `t232`'s two comprehensions and `g25_016`'s nested `emit` are functions of the
program even though the hybrid does not see them as top-level candidates.

Whole-module "typed" is the default `compile --syntax python` path (no `built on the general path`
note).  "Hybrid" is `build --cpython`; only a typed top-level function whose body the hybrid can
prove non-trapping is wrapped, so `main` and nested comprehensions are never accelerated.

| Program | Hot function (own-time share of program functions) | Module typed? | Hybrid before | First reason before / after this job |
| --- | --- | --- | --- | --- |
| `gdev/g22_014.py` | `hamming_weight` 57.5%, `main` 42.5% | yes | **yes** (`hamming_weight`) | none; unchanged |
| `gdev/g22_022.py` | `main` 59.7%, `shift_and_add_multiply` 40.3% | yes | no | `a call can raise or have side effects` (`abs(a)`/`abs(b)`) -> **`shift_and_add_multiply` accelerated** |
| `dev/t078.py` | `main` 100% | yes | no | `main` is the entry point and prints; never a hybrid unit (`unresolved-return`) |
| `corpus/.../t419.py` | `main` 100% | **no** | no | `showing a computed Decimal that may be None; bind it to a name first` -- follow-up (the Decimal prelude is not a typed library) |
| `dev/t232.py` | genexpr line 19 39.6%, genexpr line 11 33.8%, `main` 26.6% | yes | no | comprehensions are nested functions and `main` is the entry; no hybrid candidate |
| `gdev/g21_038.py` | `encode_rounded_floats` 62.3%, `main` 37.7% | yes | no | `unresolved-return` (pymix cannot prove the `json.dumps` result is a str) -- follow-up; even after that proof the body has `round(v, places)` with a variable `ndigits` and `json.dumps`, both refused as calls |
| `corpus/.../t139.py` | `main` 74.3%, `fmt` 21.7% | yes | no | `a call can raise or have side effects` (`int(value)` where `value` is a float: NaN/out-of-int64) -- follow-up |
| `gdev/g25_016.py` | `emit` 35.5%, `tokenize` 33.6%, `Token.__str__` 16.4% | **no** | no | `'_ail_en_CharClass_all' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant.` -- follow-up |

`g25_016` uses `classify` (9.3%) next; its return kind is the enum class, outside the mixed-mode
ABI.  `t419` and `g25_016` remain on the general path as a whole, so their `main` is CPython under
the hybrid.

## Compiler changes

* `AIL_CURRENT/ail_cpython_hybrid.py`: `_safe_call` accepts `abs` of a provably float argument, and
  `abs` of a provably int argument when the clone returns `int`/`bool` (only then does the existing
  overflow wrapper route `abs(INT64_MIN)` back to CPython).  It also accepts `str(<number>)` and
  `int(<int/bool>)`, which cannot raise; `int(<float>)` stays refused.  `_unsafe_body` now receives
  the result kind and tracks int/float parameter kinds for those proofs.
No int can wrap silently: an int/bool-returning clone whose arithmetic or `abs` overflows sets the
existing overflow signal and the call site runs the original Python function.

## Follow-ups (left, with the compiler's exact message)

* `g25_016`: module-level tables of enum/dataclass members (the generated enum member list and map
  are module-level containers of class instances):
  `'_ail_en_CharClass_all' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant.`
* `t419`: typed `decimal.Decimal` (the prelude itself uses dunder methods and module-level class
  instances the typed path cannot compile):
  `showing a computed Decimal that may be None; bind it to a name first`
* `t139.fmt`: a clone that can convert a float to int needs a fallback for NaN/Outflow as well as
  int64 overflow; today the hybrid says `a call can raise or have side effects`.
* `g21_038.encode_rounded_floats`: pymix first says `unresolved-return` because it does not prove
  `json.dumps(...)` returns `str`; after that proof the body's `round(v, places)` (variable
  `ndigits`, including negative values the typed runtime refuses) and `json.dumps` are calls the
  hybrid still refuses as `a call can raise or have side effects`.

## Verification

* All eight programs build with `build --cpython`; stdout and exit status equal CPython on every
  supplied corpus input (`t078`, `t139`, `t232`, `t419`: three inputs each; the four fixed programs
  once).  `g22_014.hamming_weight` and `g22_022.shift_and_add_multiply` are accelerated.
* `AIL_CURRENT/test_ail_prog21.py` (registered through `AIL_CURRENT/tests.d/`) compiles the six
  whole-module typed programs and compares them with CPython, and builds the hybrid for
  `g22_022`, `t139`, `g21_038` plus `abs` and `str` probes.  It asserts the new accelerations and
  that `fmt` and `encode_rounded_floats` stay in CPython for the named reasons.
* Probes (`/tmp/probes`), both `cmp.sh` builds unless noted:
  `p21_flist.py`, `p21_flist_min.py`, `p21_flist_min2.py`, `p21_abs_min.py`,
  `p21_abs_sources.py` (argument, list item, attribute and dict value, both signs, zero),
  `p21_strconv_min.py` (finite, `-0.0`, inf, `-inf`, NaN), `p21_g22.py`, `p21_jsonret.py` -- all
  same stdout as CPython on general and typed builds.
  `p21_abs_bound.py` is hybrid-only: `abs(INT64_MIN)`, the int64 maximum, bools and small ints all
  equal CPython (the overflow falls back); the standalone typed build intentionally stops loudly
  on `abs(INT64_MIN)` as the declared int64 behaviour.
* Generated C for all ten `lab/compare/src/*/main.ail` tasks is byte-identical between `HEAD` and
  this tree (10/10 `program.c` SHA-256 equal).
