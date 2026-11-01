# `typing` coverage (job-std_typing-11012337)

Environment: CPython 3.12.3, the default build `python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python`
(typed path first, general path as the fallback). Date: 2026-11-01.

## Before the fixes

| program | result | first message |
| --- | --- | --- |
| 01_annotations.py | general | typed path refused `int | float`; the general path printed CPython's output |
| 02_typevars.py | general | typed path refused `list[T]`; the general path printed CPython's output |
| 03_generic_class.py | general | typed path refused `class Box(Generic[T])`; the general path printed CPython's output |
| 04_namedtuple.py | general | typed path refused the `NamedTuple` dunder methods; the general path printed CPython's output |
| 05_typeddict.py | refused | `not in the subset: inheritance from 'TypedDict' (class 'Movie'); a class here may only derive from a class defined earlier in this program (the general path could not build this program either); general path: class Movie bases on TypedDict, defined after it or unknown` |
| 06_typeddict_functional.py | refused | `not in the subset: `c` is a list or dict that gets the bool `False` among other values; Python keeps each element's own type (True / 1) (the general path could not build this program either); general path: keyword arguments in a call through a function value` |
| 07_newtype.py | refused | `not in the subset: 'uid' is annotated UserId, which this compiler has no rule for (the general path could not build this program either); general path: the name 'NewType' is not a known function/class/builtin` |
| 08_cast.py | refused | `not in the subset: 'value' is annotated Any, which this compiler has no rule for (the general path could not build this program either); general path: the name 'cast' is not a known function/class/builtin` |
| 09_literal_final.py | general | typed path refused the `Literal` / `Final` annotation; the general path printed CPython's output |
| 10_protocol.py | refused | `not in the subset: inheritance from 'Protocol' (class 'Greeter'); a class here may only derive from a class defined earlier in this program (the general path could not build this program either); general path: a constant of type ellipsis` |
| 11_introspection.py | refused | `not in the subset: call to get_origin(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one (the general path could not build this program either); general path: the name 'get_origin' is not a known function/class/builtin` |
| 12_get_type_hints.py | refused | `not in the subset: 'weights' is annotated sdict in the source, but the caller also supplies int; refusing rather than silently choosing one (the general path could not build this program either); general path: the name 'get_type_hints' is not a known function/class/builtin` |

Before: 5 of 12 built (all on the general path), 7 refused.

## After the fixes

| program | result |
| --- | --- |
| 01_annotations.py | general |
| 02_typevars.py | general |
| 03_generic_class.py | general |
| 04_namedtuple.py | general |
| 05_typeddict.py | general |
| 06_typeddict_functional.py | general |
| 07_newtype.py | general |
| 08_cast.py | general |
| 09_literal_final.py | general |
| 10_protocol.py | refused (follow-up) |
| 11_introspection.py | refused (follow-up) |
| 12_get_type_hints.py | refused (follow-up) |

After: 9 of 12 build (all on the general path) and all 9 match CPython's stdout and exit code. The test
`AIL_CURRENT/test_ail_std_typing.py` (registered by `tests.d/test_ail_std_typing.txt`) compiles every passing
program in the default mode, runs it and compares both exit code and stdout with CPython. It also has a
TypedDict / NewType / cast boundary program and checks that the three follow-ups are refused by name.

## What was fixed

* `typing` was missing from the stdlib-5 rewrite gate in `ail_syntax.python_surface`, so a program whose only
  library import was `typing` never reached `stdlib5.rewrite_text` (which already listed `typing` in its words).
  The gate now includes `typing`.
* New `python/pkg-v12/typinglib.py` (called from `stdlib5.rewrite_text`) lowers the run-time parts to ordinary
  Python:
  * a `TypedDict` class declaration, a class deriving from one, and the functional
    `X = TypedDict("X", {...})` form (including `total=False` and keyword fields) become plain dicts; every
    use of the declared name is read as `dict`, and the declaration is dropped.  A constructor call with only
    `**data` is lowered to `dict(data)`, the copy CPython's `TypedDict(**data)` makes.
  * `X = NewType("X", Base)` keeps CPython's call: `UserId(7)` returns the argument `7` itself (identity), a
    call with another arity or with a keyword raises `TypeError`, and an alias of `X` stays callable. A use of
    `X` that is not a call reads as an identity function, not CPython's NewType object; the base (including a
    chain whose base is another NewType) is checked but not evaluated, and the declaration is dropped.
  * `cast(T, value)` becomes `value` (CPython's cast has no run-time effect).
  Only these three names are taken out of `from typing import ...`; every other typing name is left for the
  ordinary annotation handling.

The typed path still refuses a plain `dict` annotation in these programs, so the default build takes the
general path; there the dicts are boxed and the printed values match CPython.

## Follow-ups (need a larger feature, not fixed here)

* `10_protocol.py` -- `typing.Protocol` class bases (structural typing / interface classes):
  `not in the subset: inheritance from 'Protocol' (class 'Greeter'); a class here may only derive from a class
  defined earlier in this program (the general path could not build this program either); general path: a
  constant of type ellipsis`
* `11_introspection.py` -- `typing.get_origin` and `typing.get_args`, which need typing objects such as
  `List[int]` / `Union[int, str]` to exist as run-time values:
  `not in the subset: call to get_origin(); this compiler builds only the builtins it names, and refuses the rest
  by name rather than guessing at one (the general path could not build this program either); general path: the
  name 'get_origin' is not a known function/class/builtin`
* `12_get_type_hints.py` -- `typing.get_type_hints`, which needs function annotations as run-time objects:
  `not in the subset: 'weights' is annotated sdict in the source, but the caller also supplies int; refusing
  rather than silently choosing one (the general path could not build this program either); general path: the
  name 'get_type_hints' is not a known function/class/builtin`
