# Typed reach for the eight prog8 programs

Profile: CPython 3.12 `cProfile`, own time (`tottime`), `main()` repeated so a sub-millisecond run
has a stable profile (2000-10000 repetitions; `t396` and `t176` use `lab/corpus/tasks/*/in2.txt`).
Percentages are of the profile total excluding the profiling driver. Rows are the top functions
until at least 80% of the own time is covered.

Status is the typed path before this job (whole-program `pyc.to_c`, and `pyfunc.to_c(entry=...)` for
one function with the module's other definitions present). "typed" means no general-path note.
`library` rows are CPython stdlib frames in the profiled oracle; they are not top-level AIL
functions, and their AIL replacements are reached through the program function that calls them.

## t396 bank queue (`lab/census/programs/dev/t396.py`)

| hot function | own % | cum % | typed path |
| --- | ---: | ---: | --- |
| `random.randrange` | 24.35 | 24.35 | library (AIL import helper) |
| `random._randbelow_with_getrandbits` | 18.69 | 43.04 | library |
| `main` | 17.39 | 60.43 | no: `Random.randrange must take plain positional arguments, no defaults, *args or **kwargs` |
| `random.randint` | 10.28 | 70.71 | library |
| `_operator.index` | 8.98 | 79.70 | built-in |
| `builtins.max` | 8.56 | 88.26 | built-in |

Follow-up (big: the `random.Random` method surface): compile `random`.
The hot loop itself is inside `main`, so even a typed `main` would still call those methods.

## z-scores (`lab/census/programs/gdev/g03_018.py`)

| hot function | own % | cum % | typed path |
| --- | ---: | ---: | --- |
| `fractions.Fraction.__new__` | 12.26 | 12.26 | library (exact statistics internals) |
| `statistics._ss` | 9.41 | 21.68 | library |
| `fractions.Fraction._add` | 9.40 | 31.07 | library |
| `math.gcd` | 7.17 | 38.25 | built-in |
| `fractions.Fraction.forward` | 6.87 | 45.11 | library |
| `main` | 6.44 | 51.55 | no: `statistics.pstdev of floats needs CPython's exact fractions over floats, which is not built; ...` |
| `fractions._from_coprime_ints` | 5.72 | 57.27 | library |
| `sum` | 5.00 | 62.27 | built-in |
| `statistics.<genexpr>` (2 rows) | 5.36 | 67.63 | library |
| `round` | 2.83 | 70.46 | built-in |
| `print` | 2.55 | 73.01 | built-in |
| `fractions.Fraction.reverse` | 2.38 | 75.39 | library |
| `fractions.Fraction._div` | 2.23 | 77.62 | library |
| `statistics.pstdev` | 1.83 | 79.45 | library |
| `float.as_integer_ratio` | 1.61 | 81.06 | built-in |

`z_scores` is the other program function (about 1.3% own in the earlier run) and has the same
`statistics.pstdev` refusal. `main` is refused only because its callee is.
Follow-up (big: exact-ratio `pstdev` over floats).

## LU decomposition (`lab/census/programs/gdev/g23_032.py`)

| hot function | own % | cum % | typed path |
| --- | ---: | ---: | --- |
| `lu_decompose` | 11.59 | 11.59 | no: `dunder method Fraction.__float__; only __init__ is supported here, no other dunder (__eq__, __repr__, __len__, __add__, ...)` |
| `Fraction.__new__` | 9.30 | 20.88 | library (`_ail_fr_*` helpers) |
| `format_matrix` | 8.96 | 29.84 | no: the same `Fraction` class refusal |
| `Fraction.forward` | 6.65 | 36.49 | library |
| `Fraction._from_coprime_ints` | 5.04 | 41.53 | library |
| `main` | 4.73 | 46.25 | no: the same `Fraction` class refusal |
| `object.__new__` | 4.55 | 50.81 | built-in |
| `Fraction.__str__` | 4.16 | 54.97 | library |
| `str.join` | 4.06 | 59.03 | built-in |
| `format_matrix` genexprs (2 rows) | 7.36 | 66.39 | the same function |
| `Fraction._sub` | 3.36 | 69.75 | library |
| `sum` | 3.32 | 73.07 | built-in |
| `isinstance` | 2.99 | 76.06 | built-in |
| `print` | 2.94 | 79.00 | built-in |
| `max` | 2.52 | 81.53 | built-in |

Follow-up (big: the general `fractions.Fraction` dunder surface).

## moving average (`lab/census/programs/gdev/g03_020.py`)

| hot function | own % | cum % | typed path |
| --- | ---: | ---: | --- |
| `main` | 43.50 | 43.50 | typed |
| `print` | 22.86 | 66.36 | built-in |
| `simple_moving_average` | 12.00 | 78.36 | typed |
| `sine_series` | 8.59 | 86.96 | typed |
| `list.append` | 6.13 | 93.08 | built-in |
| `math.sin` | 5.79 | 98.88 | built-in |

The whole program was already typed; nothing to fix. (`main` is 43% own because the f-string and
formatting work is there.)

## shell sort (`lab/census/programs/gdev/g04_010.py`)

| hot function | own % | cum % | typed path |
| --- | ---: | ---: | --- |
| `shell_sort` | 26.51 | 26.51 | no: `'items' is a list parameter, which is read-only; to change it in a helper, keep the list in a struct field and pass the struct (...), or build and return a new list` |
| `main` | 25.18 | 51.69 | no: the same list-parameter refusal (through `shell_sort`) |
| `gapped_insertion_sort` | 24.58 | 76.28 | no: the same list-parameter refusal |
| `print` | 12.48 | 88.76 | built-in |
| `knuth_gaps` | 6.42 | 95.18 | typed |
| `list.append` | 2.71 | 97.89 | built-in |
| `len` | 2.08 | 99.97 | built-in |

Follow-up (big: mutating a `list` parameter and making the mutation visible to the caller).

## JSON records (`lab/corpus/programs/deepseek-v4.1-flash-free/t176.py`)

| hot function | own % | cum % | typed path |
| --- | ---: | ---: | --- |
| `json.decoder.raw_decode` | 50.26 | 50.26 | library |
| `print` | 9.62 | 59.87 | built-in |
| `main` | 6.42 | 66.30 | no: `json.loads(s): the type of the result is not declared here; write the type down: ...` |
| `sum` | 4.87 | 71.17 | built-in |
| `active_names` genexpr | 4.59 | 75.76 | the `active_names` function |
| `sorted` | 4.51 | 80.28 | built-in |
| `average_score` genexpr | 4.45 | 84.73 | the `average_score` function |
| `json.decoder.decode` | 2.54 | 87.27 | library |
| `json.loads` | 1.47 | 88.74 | library |
| `re.Match.match` | 1.29 | 90.03 | built-in |
| `average_score` | 1.23 | 91.26 | no: the `json.loads` refusal (through `main`/`load_records`) |
| `load_records` | 1.12 | 93.57 | no: the `json.loads` refusal |
| `active_names` | 0.93 | 96.52 | no: the `json.loads` refusal (through `main`/`load_records`) |

Follow-up (big: an inferred/declarative type for `json.loads`, and `list[dict[str, Any]]`).

## palindromic substrings (`lab/census/programs/gdev/g09_012.py`) - fixed

| hot function | own % | cum % | typed path before | after |
| --- | ---: | ---: | --- | --- |
| `count_palindromic_substrings` | 81.06 | 81.06 | no: `a nested annotation (a list of lists) is not a records parameter; one level of rows is recognised, not two` | **typed** |
| `main` | 9.61 | 90.66 | no: the same nested annotation, through its callee | **typed** |
| `print` | 8.41 | 99.07 | built-in | built-in |
| `len` | 0.91 | 99.98 | built-in | built-in |

The fix is in `python/pkg-v12/nested_lists.py`: a `list[list[bool]]` annotation now builds a hidden
`_AilRow_bool` row whose field is `list[bool]`. `boolkind` rewrites that field to the int spelling
and records it as a bool list, exactly like a flat `list[bool]`, so reads still print `True`/`False`
and a number stored into a bool row is still refused (or stays on the general path).
The unannotated `[[False] * n ...]` form is still inferred as `int` and remains a follow-up
(`field 'v' is a list or dict that gets bools and numbers (Python keeps each element's own type)`).

## first non-repeating character (`lab/census/programs/gdev/g05_014.py`)

| hot function | own % | cum % | typed path |
| --- | ---: | ---: | --- |
| `count_characters` | 35.06 | 35.06 | typed |
| `dict.get` | 24.77 | 59.83 | built-in |
| `main` | 19.16 | 78.99 | typed |
| `print` | 18.41 | 97.40 | built-in |
| `first_non_repeating` | 2.07 | 99.46 | typed |

The whole program was already typed; nothing to fix.

## Summary

- Hot program functions newly typed: `count_palindromic_substrings`, `main` (g09).
- Already typed hot program functions: all of g03_020, all of g05, `knuth_gaps` in g04.
- Left as follow-ups (all big, exact messages above): the `random.Random` method surface;
  exact-ratio `statistics.pstdev`; the `fractions.Fraction` dunder surface; mutating a `list`
  parameter; `json.loads` result typing / `list[dict[...]]`; unannotated nested bool lists.
- Large blockers `main` in t396/g03_018/g23/g04/t176 only because their callees are refused.
