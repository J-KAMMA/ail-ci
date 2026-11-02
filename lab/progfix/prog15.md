# prog15: typed reach of the hot functions in eight real programs

CPython 3.12, `cProfile -s tottime`, 2026-11-02.  The eight programs are the ones named by the job.
For each program the table lists the functions that together hold 80% of the program's own time
(import/startup frames and `{built-in method exec}` excluded).  "Typed before" is the state of the
base commit (`1a44d82`); "Typed after" is this job.

## Hot functions and their typed-path status

| Program | Hot function(s) (own time) | Typed before | First reason before | Typed after |
| --- | --- | --- | --- | --- |
| `gdev/g14_030.py` | `main`, `print_summary`, `build_tasks`, `group_by_priority` (all ~0.000 s; the program is startup-bound) | no | `'_ail_en_Priority_all' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant.` (enum/dataclass expansion also adds 40 dunder blockers) | no (follow-up) |
| `gdev/g17_008.py` | `parse_version` 62 calls, `<genexpr>` 235 calls, `compare_versions` 31 calls (~0.000 s each) | no | `call to tuple(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one.` (the sort retry later reports `key= must be a lambda or a function name.`) | no (follow-up) |
| `dev/t186.py` | `main` (json load/dump/reload; ~0.000 s) | no | `json.loads(s): the type of the result is not declared here; write the type down: data: dict[str, int] = json.loads(s)` | no (follow-up) |
| `corpus/.../t012.py` | `main` (read/split/multiply; ~0.000 s) | **yes** | -- | yes (unchanged) |
| `gdev/g25_024.py` | `main`, `area`, `describe` (all ~0.000 s; dataclass creation is the startup cost) | no | `'shape' is annotated Circle \| Rectangle \| Square \| Triangle \| Ellipse, which this compiler has no rule for.` | no (follow-up) |
| `gdev/g16_008.py` | `unique_vowels`, `main` (~0.000 s) | no | `'found' is declared sset; assigning int is unsupported.` (the set comprehension is not built); the module constant `VOWELS = frozenset("aeiou")` is the earlier `_to_c_once` refusal | no (follow-up) |
| `gdev/g02_000.py` | `sum_of_primes_below` 0.055 s, `sieve_of_eratosthenes` 0.006 s (98% of program time) | **yes** | -- | yes (unchanged) |
| `gdev/g08_018.py` | `determinant` 14 calls, `minor` 13 calls, `<genexpr>` 20 calls (~0.000 s; the only work in the program) | no | `a comprehension target that is not a name` (`minor`, line 10: `for j, value in enumerate(r)`) | **yes** (`determinant`, `minor`, `main`) |

`g02_000`'s hot function is typed, but `ail build --cpython` still leaves it in CPython because the
hybrid body gate refuses indexing/calls (`indexing can raise`).  That is the hybrid's conservative
safety rule, not the typed compiler; it is unchanged here.

## Fixed reason

The reason that could be fixed without a new language feature was `a comprehension target that is
not a name`.  `nested_lists.py` already lowered the outer row comprehension; the inner row
comprehension still bound a pair.  The fold path (`sum`/`max`/`min`) already walked pair targets via
`_pair_plan`; the list-comprehension path now does too (`_listcomp_kind` and a new
`_listcomp_pair_into_temp`).  `enumerate`, `zip` (both key and value keep their source kind: int,
float or str) and an unannotated dict's `.items()` work, for int- and str-keyed tables; the result
may be a list of int, float or str.  A bytes-keyed unannotated dict is refused by name, and a typed
`dict[...]`'s `.items()` still falls back with `a pair target over Call` (both match CPython on the
general path).  `g08_018` becomes fully typed and its output matches CPython.

A later probe found a silent difference in that new path: the pair value was registered in
`ctx.onecp`/`ctx.len1_names` whenever it was a str, so `_one_cp` claimed a length of 1 and
`if v != "":` kept every empty string.  Pair elements are full `ail_str` values (a str used as an
iterable is refused by `_iter_plan`), so the names are no longer registered there; string
inequality uses `ail_str_eq`.  String keys were never registered and are unchanged.  Regression
cases `enum_nonempty` / `zip_nonempty` are in `test_ail_prog15.py`.

## Follow-ups (big new features, exact current messages)

* `g14_030`: enum/dataclass expansion on the typed path.  First whole-program message:
  `'_ail_en_Priority_all' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant.`
  The strict ranking also reports `dunder method _AilEnum.__repr__; only __init__ is supported here, no other dunder`.
* `g17_008`: `tuple(...)` construction, variadic tuple returns (`tuple[int, ...]`) and tuple
  concatenation are refused by design.  Exact message:
  `call to tuple(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one.`
  The sort lowering then reports `key= must be a lambda or a function name.`
* `t186`: a dynamic JSON value has no static type.  Exact message:
  `json.loads(s): the type of the result is not declared here; write the type down: data: dict[str, int] = json.loads(s)`
* `g25_024`: union annotations and `match` class patterns.  Exact message:
  `'shape' is annotated Circle | Rectangle | Square | Triangle | Ellipse, which this compiler has no rule for.`
* `g16_008`: a set comprehension (`{ch for ch in text.lower() if ...}`) and a module-level
  `frozenset("aeiou")`.  Exact messages:
  `'found' is declared sset; assigning int is unsupported.` and
  `'VOWELS' is a module-level name assigned to a Call, not a literal; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant`.
* Typed `dict[...]` `.items()` in a pair-target comprehension/fold: still
  `a pair target over Call`; the unannotated `DICT` tables (int-, str-keyed) are the ones the typed
  pair path reads.
