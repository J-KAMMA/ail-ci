# prog6: typed reach for eight real programs

Profiled with CPython 3.12 and `python3 -m cProfile -s tottime <program>` (t402 with
`lab/corpus/tasks/t402/in0.txt`).  Every program is tiny, so all self times round to `0.000 s`;
the table names the functions that do the work (the ones that would hold 80% of a scaled run).
"Typed before" is the CPython-hybrid mixed-mode unit set before this job; "first reason" is the
first selection refusal for the hot function.

| program | hot function(s) | typed before | first reason before | result |
| --- | --- | --- | --- | --- |
| `lab/census/programs/gdev/g19_038.py` | `minutes_until_next_full_hour` | no | `unresolved-param now` (a `datetime` value has no mixed ABI) | follow-up: datetime arguments/results |
| `lab/census/programs/gdev/g09_000.py` | `fibonacci_mod` | no | `unresolved-return: return branches require distinct tags` (the `dp` annotated list and its item read were unresolved) | **typed** (`fibonacci_mod`), int overflow falls back to CPython |
| `lab/census/programs/gdev/g08_022.py` | `generate` | no | `unresolved-return: return branches require distinct tags`, then `to_c-refused: generate(): the default for 'prefix' must be a compile-time int, float or bool constant (a list, dict, str or None default is refused).` | follow-up: `list[str]` parameters/returns, recursion and a str default |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t402.py` | `hand_total`, `card_value` | no | `card_value`: `a call can raise or have side effects`; `hand_total`: `unresolved-param cards` | **typed** (`card_value`); follow-up for `hand_total`: `parameter kind list[str] stays in CPython` |
| `lab/census/programs/gdev/g21_024.py` | `flatten`, `to_json_string`, `json_to_flat_rows`, `rows_to_csv_string`, `build_sample_data` | no | `unresolved-param obj` / `records` / `rows`, `unresolved-return` | follow-up: `dict[str, Any]`, `Any`, JSON and CSV objects |
| `lab/census/programs/gdev/g09_020.py` | `catalan_numbers` | no | `unresolved-return: no return, or contradictory returns` (empty-list return and the annotated `table`) | **typed** (`catalan_numbers`), list result and int overflow fall back to CPython |
| `lab/census/programs/gdev/g14_018.py` | `main` (dataclass construction/field order) | no | `unresolved-return` for `main`; `field 'name' requires a class instance` | follow-up: dataclass/class-instance fields |
| `lab/census/programs/gdev/g09_014.py` | `count_no_adjacent_ones` | no | `unresolved-return: return branches require distinct tags` (the tuple assignment and annotated locals were unresolved) | **typed** (`count_no_adjacent_ones`) |

## Compiler fixes

1. `pymix` reads annotations as kind hints: annotated assignments (`table: list[int] = ...`) and
   the return annotation, both `list[T]` and `typing.List[T]` spellings.  A *parameter* annotation
   is deliberately not seeded: CPython never enforces it, and seeding it let a lying annotation
   compete with contradictory call-site evidence (a probe with `show([1, 2])` on `x: int` then made
   the general build emit a mismatched clone signature).  Parameters are inferred from the body and
   every call site.  The pass also infers list repetition (`[0] * n`, `n * [0.0]`), follows tuple/list
   unpacking targets, and treats `return []` in a list-returning function as that list kind.
2. A function that can finish a path with a bare `return` or by falling off the end is not a
   candidate: Python's `None` cannot travel through any scalar or list return slot.  This also
   covers the return-annotation case (`def f(n: int) -> int` with one `if ...: return 5`).
3. The CPython hybrid analysis prepares the source through the CLI's Python surface before its
   direct `pyboxed2.build` fallback, so `typing.List[int]` becomes the `list[int]` the typed emitter
   accepts.
4. The hybrid selection allows indexing, division/modulo and a tracked `raise Name(...)` when pymix
   already proved the escaping exception has no boxed caller handler.  An uncaught trap calls the
   wrapper's drain hook, which flushes Python's `sys.stdout` before `_Exit(1)`, so stdout and the exit
   status match CPython (stderr is the typed one-line message, declared in DIFFERENCES).  Only
   `range` and `int` are allowed among pure builtin calls; `float`/`ord`/`chr`/... raise exception
   types pymix does not track and stay boxed.  `assert`, an untracked raise expression, arbitrary
   calls, attribute stores and `try`/`with`/import also stay boxed.
5. A local assigned straight from a list parameter is followed as an alias, so a store through it
   cannot silently mutate only the clone's copy; the function stays in CPython.  A local list the
   function owns is still a valid clone target.
6. `pyboxed2` emits length-then-fill units for `list[int]`/`list[float]` returns; the hybrid boxes
   them, and an int64 overflow inside the clone returns `-1` so the wrapper runs the original
   CPython function.  These units are linked into a plain general build only when the hybrid capture
   asks for them, and the drain definition is emitted whenever any unit exists, so ordinary general
   C (including all ten `lab/compare` tasks) is unchanged.

The four newly typed hot functions are `fibonacci_mod`, `card_value`, `catalan_numbers` and
`count_no_adjacent_ones`.  `AIL_CURRENT/test_ail_prog6.py` builds each program and compares it with
CPython, including overflow/negative/invalid-input fallbacks, an uncaught trap after earlier output,
list aliasing, an untracked pure call and a fall-through return.  Probes in `/tmp/probes` cover the
boundaries on both standalone builds and the hybrid.
