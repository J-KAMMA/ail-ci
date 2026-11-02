# prog7: hot functions of eight real programs on the typed path

Profiles: CPython 3.12.3, `cProfile`, own time (`tottime`) of the program's own functions. Percentages
are shares of the own time of the program's own functions (module/import overhead excluded unless noted).
The 80% cut is taken over those functions; `genexpr` rows are the inline comprehensions of the function
named beside them, not separate units.

| program | hot functions (own-time share) | typed path before | first reason / follow-up |
| --- | --- | --- | --- |
| `lab/census/programs/dev/t018.py` | `main` 76.4%, `<genexpr>:15` 10.9% (87.3%) | yes (whole program) | -- |
| `lab/census/programs/gdev/g12_034.py` | `simulate` 41.9%, its `<genexpr>:45` 28.1%, `generate_arrivals` 13.9% (83.9%) | no | `Random.randrange must take plain positional arguments, no defaults, *args or **kwargs` (the imported `random` prelude). Mixed mode also rejects `simulate` with `unresolved-return` (it returns `CarWashStats`) and `generate_arrivals` with `unresolved-param rng` (`random.Random`). Follow-up. |
| `lab/census/programs/gdev/g15_018.py` | `to_float_or_nan` 52.3%, `convert_all` 14.6%, `main` 8.2% (75.1%) | yes (whole program) | -- |
| `lab/corpus/programs/glm-5.3-flash-free/t184.py` | `flatten` 43.5%, `main` 33.5% (77.0%) | no | `main`: `json.loads(s): the type of the result is not declared here; write the type down: \`data: dict[str, int] = json.loads(s)\` ...`. `flatten`: `unresolved-param value` (`Any` / `Iterator[tuple[str, Any]]`, a generator). Follow-up. |
| `lab/census/programs/gdev/g14_038.py` | `bulk_footprint` 27.0%, `total_size` 22.1%, `dict_size` 20.4%, its `<genexpr>:60` 12.4% (81.9%) | no (typed and general refuse) | `'obj' is annotated object, which this compiler has no rule for.` (also `bulk_footprint`: `unresolved-param factory`, a `Callable[..., object]`). The general path additionally refuses `sys.getsizeof (not yet published in NAMES_library.json)`. Follow-up. |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t474.py` | `process_line` 60.3%, `main` 23.7% (84.0%) | yes (whole program) | -- |
| `lab/census/programs/gdev/g10_032.py` | `largest_region` 77.4%, `main` 9.0% (86.4%) | no | first `field \`v\` is a list or dict that gets bools and numbers (Python keeps each element's own type)`, then `_AilDeque_tup2_int_int.buf has unsupported field type array; fields require a known nonnullable scalar, container or managed struct type` (the tuple lowering refused `for dr, dc in directions`). **Fixed** below. |
| `lab/census/programs/gdev/g23_038.py` | `matmul` 31.7%, `main` 17.8%, `diagonal_sum` 10.4% (module/import own time 36.7%) | yes (whole program) | -- |

Result after the fixes in this job: five of the eight programs take the typed path; `t018`, `g15_018`,
`t474`, `g23_038` already did, and `g10_032` now does. `g12_034`, `g14_038` and `t184` remain general /
CPython because their hot functions need the new features listed as follow-ups.

## What changed in the compiler

1. `nested_lists.py`: `bool` is a scalar row element kind (`SCALARS` includes `bool`; a bool constant
   types as `bool`). A `[[False] * w ...]` row becomes `_AilRow_bool` instead of sharing
   `_AilRow_int` with the grid.
2. `boolkind.py`: a field store through `x[i]` where `x` is a list of a known class (from its
   annotation or a list literal of constructors) now names that class as the receiver. Before, an
   unknown receiver reached *every* class that had a field with the same name, so `v` of
   `_AilRow_bool` and `v` of `_AilRow_int` looked like one mixed field.
3. `tuplib.py` / `tupexpr.py` / `tupstmt.py` / `tupcommon.py`: a loop over a tuple of constant
   displays is lowered to an annotated list of the same items built before the loop (evaluated once,
   in order, as CPython evaluates the tuple). The transform itself does not force the tuple pass, so
   a program whose only tuple use is such a loop keeps the source as written and its general-path C
   unchanged (`berth_sim/main.py`). Empty tuples and tuples whose items have different or unknown
   types stay refused by name.

## Follow-ups (large new features, exact messages)

* `g12_034`: class methods with defaults and `None` defaults in the `random.Random` prelude, and a
  struct return from a mixed-mode function.
  `Random.randrange must take plain positional arguments, no defaults, *args or **kwargs`
* `g14_038`: the `object` type, `Callable[..., object]`, `getattr`, and `sys.getsizeof` on the
  general path.
  `'obj' is annotated object, which this compiler has no rule for.`
  `sys.getsizeof (not yet published in NAMES_library.json)`
* `t184`: an unannotated `json.loads` result and `typing.Any` / generator values.
  `json.loads(s): the type of the result is not declared here; write the type down: \`data: dict[str, int] = json.loads(s)\` (the types are int, float, str, bool, list[T], list[list[T]], dict[str, T])`
