# prog16: typed reach of eight real programs

Method: each program ran under CPython 3.12 with `cProfile`; the table keeps the program's own
functions in own-time order until they hold 80% of the program's own function time (library/builtin
frames are excluded, since the hybrid leaves those in CPython). "Typed" means the function reaches
the typed path, either because the whole program compiles typed (`AIL_NO_GENERAL=1`) or, when the
program falls back, because mixed mode (`pymix.analyze` + `pyfunc.to_c`) selects it as a typed
clone. The first reason is the first `--strict` / mixed-mode refusal for that function.

| Program | Hot functions (own time, cumulative) | Typed before | First reason before | Typed after |
| --- | --- | --- | --- | --- |
| `dev/t268.py` | `main` 78.6%, two `<genexpr>` 6.8/2.9% (88.3%) | no | `a comprehension target that is not a name` (`[i for i, d in enumerate(degree) ...]`, line 29) | **yes**, whole program typed on `AIL_IR=0/1` |
| `dev/t068.py` | `main` 75.1%, `<genexpr>` 16.2% (91.3%) | yes | -- | yes, unchanged |
| `t003.py` | `main` 87.4% | yes | -- | yes, unchanged |
| `gdev/g21_034.py` | `make_patch` 57.7%, `main` 13.6%, `escape_pointer_token` 11.2% (82.4%) | no | `only a class type can be None` (`ops: list[dict[str, Any]] \| None`); mixed mode: `unresolved-param before, after, path, ops` | no, follow-up |
| `gdev/g09_028.py` | `main` 47.6%, `min_jumps` 33.3% (80.9%) | yes | -- | yes, unchanged |
| `gdev/g20_038.py` | `<module>` 30.5%, `expand_text` 14.5%, `main` 13.0%, `expand` 13.0%, `<genexpr>` 10.9% (81.9%) | no | general path: `re.compile (not yet published in NAMES_library.json)`; typed: `'pattern' is annotated re.Pattern[str], which this compiler has no rule for.` and `returning a nested function ('expand') is not available` | no, follow-up |
| `gdev/g14_040.py` | `from_dict` 39.3%, `_convert` 25.5%, `main` 17.6% (82.4%) | no | general path: `the name 'get_origin' is not a known function/class/builtin`; typed: `parameter v of _ail_dcv() gets a bool from some calls and a number from others; Python keeps each value's own type and a number would print as 1 / 0.`; mixed mode: `unresolved-param tp, value` / `cls, data` | no, follow-up |
| `gdev/g25_038.py` | `describe` 60.5%, `main` 18.1%, `to_celsius` 6.9% (85.5%) | no | `'READINGS' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant.` | **yes**, whole program typed on `AIL_IR=0/1` |

No program file was edited.

## Fixed in the compiler

1. **Pair comprehension over `enumerate`.** `pyfunc._listcomp_kind` and `_listcomp_into_temp`
   accepted only a plain name target, so `[i for i, d in enumerate(xs) if ...]` kept all of
   `t268.main` on the general path. They now recognise a two-name tuple target over `enumerate` and
   reuse `_pair_plan` (the same plan the existing pair folds use); both names are bound as ints and
   the result is built by the ordinary list/temp path. `enumerate(..., start=...)`, a list of
   floats and a list of str stay refused by name, as the pair-fold rules already required. This is
   what makes `t268` fully typed.
2. **Module-level list of tuples with negative float literals.** `modtables._scalar` accepted
   `-1` (via `_int_value`) but not `-1.5`, so `READINGS: Final[list[tuple[float, str]]]` looked
   like a list of non-numbers and `g25_038` stayed general. Unary `-` / `+` over a float literal is
   now a scalar of kind float (`-0.0` keeps its sign), so the existing tuple-table lowering builds
   the table and passes it to the functions that read it. This is what makes `g25_038` fully typed.

## Follow-ups (large features, left as exact messages)

* `g21_034`: `Any` parameters, `list[dict[str, Any]]` parameters and `X | None` for a non-class,
  then `json.dumps of operations: the type of this value is not known here ...`.
* `g20_038`: the general path needs `re.compile`, `re.Pattern`, `re.Match` and a returned nested
  function: `re.compile (not yet published in NAMES_library.json)`, `'pattern' is annotated
  re.Pattern[str], which this compiler has no rule for.`, `'match' is annotated re.Match[str],
  which this compiler has no rule for.`, `returning a nested function ('expand') is not available`.
* `g14_040`: typing reflection (`typing.get_origin`, `get_args`, `get_type_hints`) and
  `dataclasses.fields(cls)` with a variable, plus the bool/number mixture in generated `_ail_dcv`:
  `the name 'get_origin' is not a known function/class/builtin` and
  `parameter v of _ail_dcv() gets a bool from some calls and a number from others`.
