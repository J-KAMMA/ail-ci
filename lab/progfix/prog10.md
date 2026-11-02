# Typed reach: eight real programs (job-prog10-11020733)

CPython 3.12 `cProfile`, own time (`tottime`) over repeated `main()` calls. The percentages are of the
program's total profiled time; the functions listed are every user-defined function hot enough to matter.
The remaining time is in CPython builtins (`print`, `isinstance`, `sorted`, ...), which AIL does not type.
"Typed" means the whole program is accepted by the typed path (then every function in it is typed); a
program the typed path refuses has no typed function, even when one function in isolation might qualify.

| Program | Function | Own time | Typed? | First reason / follow-up |
| --- | --- | ---: | --- | --- |
| `g13_014` | `Comparable.__init__` | 17.4% | no | ``the result of __lt__() is declared bool, but `NotImplemented` is not a bool (Python would keep the number and print it as one); return a bool: True/False, a comparison, `not`, or `NotImplemented != 0`` (line 12) |
| `g13_014` | `Comparable.__lt__` | 16.8% | no | same class-level refusal |
| `g13_014` | `<genexpr>` | 14.5% | no | same class-level refusal |
| `g13_014` | `main` | 8.5% | no | same class-level refusal |
| `g13_014` | `Version.key` | 4.6% | no | same class-level refusal |
| `g13_014` | `Version.__str__` | 1.3% | no | same class-level refusal |
| `g06_036` | `main` | 42.8% | no | `itertools: the loop target has to be a name or a tuple of names` (line 13) |
| `g06_036` | `pairwise_overlaps` | 11.1% | no | same refusal; the loop is `for (i, a), (j, b) in combinations(enumerate(point_sets), 2)` |
| `g06_036` | `interval_to_set` | 7.4% | no | same refusal (the whole program stops before this function) |
| `g06_036` | `<genexpr>` | 2.8% | no | same refusal |
| `g07_038` | `main` | 46.0% | yes | whole program typed |
| `g07_038` | `product_except_self` | 26.6% | yes | whole program typed |
| `g06_016` | `letters_in` | 37.9% | no | `letters_in() typed dict return disagrees with its annotation` (line 11) |
| `g06_016` | `missing_letters` | 22.7% | no | same refusal |
| `g06_016` | `main` | 14.9% | no | same refusal |
| `g01_016` | `parse_records` | 40.1% | no | `a nested annotation (a list of lists) is not a records parameter; one level of rows is recognised, not two` |
| `g01_016` | `main` | 11.5% | no | same refusal |
| `g01_016` | `largest_record_index` | 4.0% | no | same refusal |
| `t016` | `main` | 53.3% | yes | whole program typed |
| `g11_016` | `is_valid` | 31.6% | yes | whole program typed |
| `g11_016` | `solve` | 23.3% | yes | whole program typed |
| `g11_016` | `find_empty` | 15.2% | yes | whole program typed |
| `g11_016` | `<genexpr>` | 13.8% | yes | whole program typed |
| `g25_030` | `find_completions` | 32.6% | yes | was ``this use of a str as an iterable is not built (plain `for c in s` is); for an index keep a counter: `let i = 0; for c in s { ...; i += 1; }``; fixed |
| `g25_030` | `main` | 20.2% | yes | whole program typed after the fix |
| `g25_030` | `next_state` | 15.1% | yes | already the only function the CPython hybrid accelerated |

## What changed

`python/pkg-v12/pyfunc.py` now builds `for index, ch in enumerate(text)` over a `str` as the pair form of
the existing `for ch in text` walk: the same UTF-8 character view, evaluated once into a private temp.
`index` is bound from a private counter, so it counts characters (not bytes) and a body that rebinds the
index cannot change the next step. This removed the last refusal for `g25_030`, so the whole program is
now on the typed path (both `AIL_IR` modes); before, only `next_state` was accelerated by
`ail build --cpython`. The generated C of the ten `lab/compare/src/*/main.ail` tasks is byte-identical to
the base commit.

## Follow-ups (big features, left out)

- `g13_014`: classes/ABCs with a rich comparison that returns `NotImplemented`, plus the variable-length
  `tuple[int, ...]` field and tuple ordering.
- `g06_036`: a nested tuple loop target over `itertools.combinations`, plus `set[int]` / `tuple[int, int]`
  containers, `set().union(*point_sets)` and f-strings.
- `g06_016`: a `set[str]` comprehension (`{ch for ch in text.lower() if ...}`), `set(str)`, set
  difference and `sorted(set[str])`.
- `g01_016`: records with a nested `list[dict[str, str]]` annotation (two levels of containers).
