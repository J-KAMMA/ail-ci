# prog11: typed reach of eight real programs

CPython 3.12.3, `python3 -m cProfile -s tottime`, each program on its largest task input
(`lab/corpus/tasks/<t>/in2.txt`) or no input for the self-contained `gdev` programs.  Times are tiny
because the published inputs are tiny; the table lists every project function in own-time order and
the share is of the whole profiled run (including interpreter/import builtins).  For the 80% cut the
project functions are `main` plus the helpers/lambdas below; where the whole-run share is dominated by
imports (`g25_006`, `t388`) the two program functions are still the only ones there are.

| program | hot function (own time) | own share | cum share | typed before | typed now | first reason before |
| --- | --- | ---: | ---: | --- | --- | --- |
| t256 | `main` | 47.7% (69 us) | 87.6% | yes | yes | -- |
| t310 | `main` | 19.0% (12 us) | 76.2% | no | no (follow-up) | `call to iter(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one.` |
| t310 | `<genexpr>` line 10 | 7.2% (5 us) | 7.2% | no | no (follow-up) | `this use of a str as an iterable is not built (plain \`for c in s\` is); ...` |
| t310 | `<genexpr>` line 6 | 5.4% (3 us) | 5.4% | no | no (follow-up) | same `iter()` reason (its source is `it`) |
| t310 | `is_subsequence` | 4.2% (3 us) | 14.3% | no | no (follow-up) | `call to iter(); ...` |
| t310 | `left_aligned_differences` | 3.2% (2 us) | 17.5% | no | no (follow-up) | `this use of a str as an iterable is not built ...` |
| g11_030 | `count_paths` | 93.7% (639 us) | 94.1% | no | **yes** | `'START' is a module-level name assigned to a Call, not a literal; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant` |
| g11_030 | `main` | 1.6% (11 us) | 96.0% | no | **yes** | same module-constant reason (`START`, `END`) |
| g25_006 | `main` | 1.4% (14 us) | 2.9% | no | no (follow-up) | `dunder method _AilIntEnum.__lt__; only __init__ is supported here, no other dunder (__eq__, __repr__, __len__, __add__, ...)` |
| g25_006 | `describe` | 0.3% (3 us) | 0.4% | no | no (follow-up) | same generated-Enum reason; also `_ail_en_CommandType_all is a module-level list of non-numbers` |
| t058 | `main` | 54.6% (2357 us) | 99.6% | yes | yes | -- |
| g11_006 | `jacobi_step` | 57.3% (996 us) | 57.7% | yes | yes | -- |
| g11_006 | `main` | 3.9% (67 us) | 62.4% | yes | yes | -- |
| g11_006 | `make_grid` | 0.7% (12 us) | 63.1% | yes | yes | -- |
| t404 | `<lambda>` line 14 | 18.6% (1218 us) | 84.5% | no | **yes** | `a tuple used where a single value is needed.` |
| t404 | `main` | 2.2% (142 us) | 99.6% | no | **yes** | same tuple reason (the keyed `min` is lowered inside `main`) |
| t388 | `main` | 8.2% (66 us) | 21.3% | no | no (follow-up) | `import of 'datetime' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |
| t388 | `<lambda>` line 15 | 2.3% (19 us) | 3.4% | no | no (follow-up) | same `datetime` reason (also `unsupported local annotation list[date].`) |

## Fixed here

1. **Annotated tuple module constants** (`python/pkg-v12/tuplib.py`).  An `AnnAssign` whose value is a
   tuple, or a non-empty list of tuples, now goes through the same `module_assign` lowering as the
   unannotated assignment.  Before, `START: tuple[int, int] = (0, 0)` reached the ordinary statement
   path, became `START = _AilT_i_i(0, 0)`, and was refused as a module constant; that blocked both hot
   functions of `g11_030`.  Scalar annotations and non-tuple values are untouched.
2. **Tuple key in `min`/`max`** (`python/pkg-v12/iterlower.py`).  `iterlower` already lowered
   `min/max(xs, key=K)` to a one-pass loop, but `K` returning a tuple made the loop compare a tuple
   value, which the typed path refuses.  A tuple-returning lambda key is now split into its components:
   each component is evaluated once per element, in order, and the loop compares them lexicographically
   with CPython's rule (test `==` component by component, and only call `<`/`>` on the first unequal
   one), exactly CPython's tuple order and its first-best tie rule.  The element is bound before the
   key runs and `len()` is re-read each step, so a key that pops or appends to the source list sees the
   same elements and stops at the same place as CPython's list iterator.  The scalar-key and
   `default=` paths are unchanged in shape.  This makes `t404` typed.
3. **Forward references to tuple module constants** (`python/pkg-v12/tuplib.py`).  Splitting `X` into
   `X__c0`, `X__c1` is now done before any function is lowered, so a function defined above the
   constant still rewrites `X[0]` to `X__c0` instead of leaving a reference to the removed module name.
   This restores the annotated form (`def f(): return X[0]; X: tuple[int, int] = (4, 5)`) and also
   builds the unannotated form that used to be refused.

Both changes affect only programs that previously were refused.  The generated C of the ten
`lab/compare` tasks is byte-identical to the base commit (all ten `main.ail` builds compared).

## Review fix: rebinding or deleting a tuple module constant

A tuple module constant is kept as columns (`START__c0`, `START__c1`), so a later rebinding or
deletion cannot be followed exactly.  `tuplib.py` now scans module-level bindings (assignment,
augmented assignment, `for`/`with`/`except`/`match` targets, imports, `def`/`class`, `del`) and
`global NAME` bindings in function and class bodies before splitting.  If one of them touches a
tuple constant, the whole tuple lowering is refused by name and the program stays on the general
path, where it matches CPython:

* `X = 9` after `X: tuple[int, int] = (4, 5)` -> `TypeError: 'int' object is not subscriptable`
  (was `4`, the stale column);
* `del X` -> `NameError: name 'X' is not defined` (was an uncaught compiler `KeyError: 'X'`);
* the same through `global X` inside a function.

Rebinding to another tuple constant (including a different component type or arity, before or
after the function call) still splits both definitions and matches CPython.

## Follow-ups (left by name)

* `lab/corpus/programs/deepseek-v4.1-flash-free/t310.py`: needs a typed `iter()` over a str and a
  str pair in a generator expression (`zip(s, t)` inside `sum(...)`); both hot helpers and `main` stay
  on the general path until then.  Exact first message:
  `call to iter(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one.`
* `lab/census/programs/gdev/g25_006.py`: needs typed `Enum`/`auto()` lowering, including the generated
  `_AilEnum`/`_AilIntEnum` dunder methods and module-level enum tables.  Exact first message:
  `dunder method _AilIntEnum.__lt__; only __init__ is supported here, no other dunder (__eq__, __repr__, __len__, __add__, ...)`
* `lab/census/programs/dev/t388.py`: needs typed `datetime` (`date.fromisoformat`, ordering,
  `list[date]`).  Exact first message:
  `import of 'datetime' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).`
  (second: `unsupported local annotation list[date].`)
