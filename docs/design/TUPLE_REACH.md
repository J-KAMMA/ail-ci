# Heterogeneous tuple reach (2026-11-01)

Question: which uses of tuples that mix element types (`(int, str, float)`, `(bool, int)`, nested tuples)
build on the typed path, which fall back to the general path, and which are refused?  This note measures
25 probe programs, records the largest fallback cause, and changes that one cause.

## Method

Probes live in `/tmp/probes/t01_*.py` .. `/tmp/probes/t25_*.py`.  Each is ordinary Python 3.12 and was run:

- with CPython (`python3 <probe>.py`), as the oracle;
- with the default build (`AIL_NO_CACHE=1`, no path flag): **typed** when the build succeeds without the
  `note: ... built on the general path` line, **general** when it succeeds with that line, **refused** when
  it does not build;
- with `AIL_NO_GENERAL=1` to confirm that a typed result is the typed path itself, and with
  `AIL_UNIFIED_FORCE=1` to confirm that a general result is the general path.

Every probe that built printed the same stdout and had the same exit status as CPython, before and after the
change.  None of the 25 was refused by both builds; the tuple pass's own notes name the forms it does not
lower, and the general path builds those.

## The 25 probes

| probe | pattern | before | after | CPython |
| --- | --- | --- | --- | --- |
| t01 | return `(int, str, float)` from constant body, unpack | typed | typed | same |
| t02 | return tuple whose element types come from an unannotated parameter | general | **typed** | same |
| t03 | list of `(int, str, float)`, `sort()` | typed | typed | same |
| t04 | list of `(str, int, float)`, `sort(key=...)`, `sorted` | typed | typed | same |
| t05 | dict keyed by `(int, str)` | typed | typed | same |
| t06 | dict keyed by `(int, str, float)` | general | general | same |
| t07 | set of `(int, str, float)`, membership, `sorted` | general | general | same |
| t08 | dict value `(int, str, float)` | typed | typed | same |
| t09 | lexicographic compare of tuples with float and str | typed | typed | same |
| t10 | nested `((int, str), float)` | typed | typed | same |
| t11 | `for a, b, c in [(...), (...)]` over a literal list | general | general | same |
| t12 | tuple passed to an unannotated parameter (argument) | general | **typed** | same |
| t13 | same through a list item | general | **typed** | same |
| t14 | tuple stored in an unannotated attribute, then printed | general | general | same |
| t15 | same through a dict value | general | **typed** | same |
| t16 | unannotated function returning a constant tuple, field reads | typed | typed | same |
| t17 | `(bool, str)` compare and print | typed | typed | same |
| t18 | `(int, bytes)` print | general | general | same |
| t19 | `(int, bytes)` compare | general | general | same |
| t20 | one list holding tuples of two different arities | general | general | same |
| t21 | iterate a tuple | general | general | same |
| t22 | variable tuple index | general | general | same |
| t23 | tuple concatenation | general | general | same |
| t24 | tuple slice | general | general | same |
| t25 | dict keyed by `(float, str)` | general | general | same |

Totals: before **9 typed / 16 general / 0 refused**; after **13 typed / 12 general / 0 refused**.

## Why the remaining 12 are general

| cause | probes | count |
| --- | --- | --- |
| a tuple operation the lowering does not build (iterate, variable index, concat, slice) | t21-t24 | 4 |
| a float inside a dict key or set element (CPython's float hash is not built) | t06, t07, t25 | 3 |
| a bytes element (no repr / compare / hash for it in the tuple lowering) | t18, t19 | 2 |
| one container holding tuples of different arities | t20 | 1 |
| a `for` over a list literal of heterogeneous tuples | t11 | 1 |
| a tuple in an attribute whose class does not declare the field | t14 | 1 |

These are separate gaps; the largest single fallback cause was the unannotated signature group below.

## The change: unannotated signatures

Before, `def g(t): return t[1], t[2]` kept the whole program on the general path even when every caller
passed the same tuple shape.  The tuple pass refused the argument ("a tuple passed to parameter ... whose
type is not told") and the source stayed as written; the typed path cannot build a heterogeneous tuple of
unknown type, so the default build fell back.

Now the pass collects the type of every argument at every call site (`tupcalls.call_user`, positional and
keyword), keeps a parameter type only when every observed call site agrees on one known type
(`observe_param` / `finish_params`), and uses it in `make_sig`.  A type that contains a tuple is spelled on
the parameter (`def g(t: _AilT_i_s_f)`); a scalar type is used only inside the pass to settle a return type
and is not written into the source.  `rewrite` repeats the lowering until the parameter types, return types
and empty-display hints stop changing (at most four rounds), because a parameter type can settle a return
type that settles a later call.

Conservative rules: an unknown call site, two different tuple shapes, or a tuple beside a scalar leaves the
parameter unannotated, so the program stays on the general path.  This is what `b02`-`b03` and `b12` below
check.  Two further rules keep an inferred type from changing a program that was already correct:

- a parameter the function body assigns to itself is never given a call-site type, because the assignment
  (possibly of another type) would be hidden by the inferred field type;
- a function that returns a tuple on one path and another type or tuple shape on another is not pulled onto
  the typed path by a parameter hint: its return type cannot be settled, so callers could print the tuple
  class instead of the tuple.  It stays on the general path, exactly as before the inference.

No C runtime code changed.

## Boundary probes for the change

`/tmp/probes/b01_*.py` .. `b18_*.py`, all compared with CPython on the default and forced-general builds:

| probes | result |
| --- | --- |
| b04 wrapper passes a tuple through two unannotated functions | typed |
| b05 keyword argument | typed |
| b09 nested tuple | typed |
| b10 INT64_MIN / INT64_MAX and `-0.0` elements | typed |
| b11 alias of a tuple | typed |
| b13 bool element reads back as `True` / `False` | typed |
| b14 unannotated `list[tuple[...]]` parameter | typed |
| b15 unannotated `dict[str, tuple[...]]` parameter | typed |
| b16 scalar value reaching the function through a list item / `len()` | typed |
| b17 tuple through an annotated attribute | typed |
| b18 argument, list item, dict value and annotated attribute together | typed |
| b02 two tuple shapes at one parameter | general, same as CPython |
| b03 tuple and scalar at one parameter | general, same as CPython |
| b12 int and float at one scalar parameter | general, same as CPython |
| b01, b06, b07, b08 | general for independent typed-path limits (unannotated class field, class without `__init__`, tuple default, two tuple shapes), same as CPython |
| b19 scalar parameter reassigned to a `str` in the body | general, same as CPython |
| b20 mixed-return method with an inferred tuple parameter (`str` or tuple) | general, same as CPython |

## Acceptance checks

- `test_ail_tuple_reach` (new, 21 tests) asserts the typed path for the 15 positive programs and the general
  path plus CPython parity for the 6 conservative ones.
- `test_ail_tuples` (26 tests) and `test_ail_typed_tuples` (10 tests) still pass.
- Generated C for the 10 `lab/compare` tasks is byte-identical between the base commit and this change for
  every build that succeeds: all 10 `main.ail`, the 5 `main.py` that build by default, and the 2 that need
  `--exact-int` (17 builds, 199,155 .. 2,223,464 bytes each).  The other 3 `main.py` programs fail
  identically on both revisions.  All 10 `main.py` tuple rewrites are identical in text; one diagnostic note
  differs and does not affect the generated C.
