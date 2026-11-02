# Typed reach, batch 12

`cProfile` own time under CPython 3.12.3.  The supplied inputs are tiny, so each `main` was run
repeatedly with the same input (and a fresh stdin) until the program's own functions were
measurable: 2,000 times for the fixed-input `gdev` programs, 1,000 for `t168`, `t378`, `t018` and
`t328`, 500 for `t328`, 200 for `t338`, and 100 for `t338` in the first pass.  The percentages are
`tottime` among the program-file functions; `<module>`, the stdlib and C builtins are not
candidates and are excluded from the ranking.

## Profile

| Program | Hot function(s), own-time share | Together |
| --- | --- | ---: |
| `gdev/g10_020.py` | `is_connected` 26.5%, `is_tree` 23.5%, `build_adjacency` 14.7%, `main` 11.8% | 76.5% |
| `corpus/.../t168.py` | `main` 90.4%, its `<genexpr>` line 19 3.8% | 94.2% |
| `dev/t338.py` | `main` 60.6%, its `<genexpr>` line 18 39.4% | 100% |
| `gdev/g15_002.py` | `parse_integers` 71.4%, `main` 28.6% | 100% |
| `gdev/g17_038.py` | `average_by_class` 45.5%, `main` 36.4%, its two lambdas 18.2% | 100% |
| `dev/t378.py` | `<genexpr>` line 11 42.1%, `main` 36.8%, `<lambda>` line 10 21.1% | 100% |
| `corpus/.../t328.py` | `_add_raw` 33.8%, `main` 26.2%, `__init__` 9.2%, `add` 4.6%, `prefix` 4.6%, `range_sum` 3.1% | 81.5% |
| `corpus/.../t018.py` | `main` 100% | 100% |

The remaining time in `g10_020` is in `set.add`/`min`/`max`/`deque` builtins, and in `t338`/`t378`
in `all`/`sorted`/`join`; those are not user functions and the typed path already lowers the ones
it supports.

## Typed path per hot function

"Typed" is the default `compile --syntax python` path.  A whole-program typed answer means every
user function in the file is typed.  The CPython hybrid only wraps a top-level function whose
result kind is in its ABI; every hot `main` below is void, and a mixed-mode `main` is refused with
`unresolved-return` ("no return, or contradictory returns"), so those programs still run wholly in
CPython under `--cpython` even when the default typed path accepts them.  That void-main ABI is
recorded as a follow-up, not silently claimed as acceleration.

| Program | Hot function | Typed? | First reason before / remaining |
| --- | --- | --- | --- |
| `g10_020` | `build_adjacency` | no | `'adj' is annotated dict[int, list[int]], which this compiler has no rule for.` |
| `g10_020` | `is_connected` | no | mixed mode: `unresolved-param adj` (a `dict[int, list[int]]` parameter has no ABI) |
| `g10_020` | `is_tree` | no | mixed mode: `unresolved-param edges` (`list[tuple[int, int]]`) |
| `g10_020` | `main` | no | the program's first refusal above; void main is not a hybrid unit |
| `t168` | `main` + genexpr | no | `unsupported local annotation dict[str, set[str]].`; also imports `csv` |
| `t338` | `main` + genexpr | **yes** | was `itertools: perm holds a tuple in CPython; here it is a list, and this use of it ...` (line 17); fixed by this batch |
| `g15_002` | `parse_integers` | yes (whole program) | mixed mode alone: `unresolved-param items` (`Iterable[str]`) |
| `g15_002` | `main` | yes (whole program) | void main is not a hybrid unit |
| `g17_038` | `average_by_class` | no | `'RECORDS' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant.`; mixed mode: `unresolved-param records` |
| `g17_038` | `main` + lambdas | no | same module-level `RECORDS` refusal (the lambdas are accepted once the list is) |
| `t378` | `main` + genexpr + lambda | yes (whole program) | void main is not a hybrid unit |
| `t328` | `Fenwick._add_raw`, `add`, `prefix`, `range_sum`, `__init__` | no | class methods are not top-level hybrid units; the field `Fenwick.tree` is a list: `Fenwick.tree would hold a list, set or dict; a field is int64, float or bytes only (SEMANTICS.md section 25)` |
| `t328` | `main` | no | general path: `call to iter()` at line 33; also void main |
| `t018` | `main` | yes (whole program) | void main is not a hybrid unit |

## Fixed here

1. **An empty variable-length tuple local becomes a `list[int]` when every use is
   list-compatible** (`python/pkg-v12/pyfunc.py`, `_rewrite_bare_tuple_locals`).  `t338` declares
   `last: tuple[int, ...] = ()`, assigns each `itertools.permutations` item to it, and only joins
   and walks the result.  The typed path already holds a permutation tuple as a list; the rewrite
   is limited to `tuple[int, ...]` and to uses where CPython's tuple and the typed list agree
   (index, loop, `join`, `len`, `sum`, `min`, `max`, `sorted`, `any`, `all`, `set`, `list`,
   `index`, `count`, `in`).  A print, equality, a slice, a dict key, a return or any other call
   leaves the annotation untouched, so the old named refusal still applies.  `tuple[float, ...]`
   deliberately stays refused: `sum(())` is CPython's int `0`, while the typed `list[float]` sum is
   `0.0`; a probe caught that difference before this guard was added.
2. **The itertools tuple check follows a plain alias** (`python/pkg-v12/itlib.py`,
   `check_nonescaping`).  `last = perm` is the same list, so the alias target's uses are checked
   with the same rules instead of the assignment itself being treated as an escape.  A use that
   can tell a tuple from a list (print, equality, a slice) still refuses by name.

## Follow-ups (big features, not implemented here)

1. **Void `main` in the hybrid ABI** -- blocks every hot `main` above.  Mixed mode refuses it with
   `unresolved-return` ("no return, or contradictory returns"); the extension ABI carries only
   scalar/list results, and a `main` clone also needs a safe stdin/stdout bridge.
2. **Dict values that are containers** (`g10_020`, and `t168.main`) --
   `'adj' is annotated dict[int, list[int]], which this compiler has no rule for.` and
   `unsupported local annotation dict[str, set[str]].`
3. **Lists of tuples / records as mixed-mode parameters and results** (`g10_020.is_tree`,
   `g17_038.average_by_class`) -- mixed mode says `unresolved-param edges` and
   `unresolved-param records`; the module table also says
   `'RECORDS' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant.`
4. **Class fields that are lists, and methods as hybrid units** (`t328`) --
   `Fenwick.tree would hold a list, set or dict; a field is int64, float or bytes only (SEMANTICS.md section 25)`;
   the hybrid selects only top-level functions, so `_add_raw`/`add`/`prefix`/`range_sum` cannot be
   wrapped today.

## Verification

`AIL_CURRENT/test_ail_prog12.py` (registered through `tests.d/test_ail_prog12.txt`) compiles `t338`
on the typed path alone (`AIL_NO_GENERAL=1`) and compares stdout/exit status with CPython on all
three task inputs.  It also checks a safe permutation local (empty and non-empty, indexing,
iteration, `len`/`sum`/`sorted`/`any`/`all`/`join`), an itertools alias without a local annotation,
the named refusal of `tuple[float, ...]`, and that unsafe tuple uses (print, equality, slice)
still match CPython through the general path.
