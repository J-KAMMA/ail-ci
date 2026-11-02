# prog19: typed reach of the hot functions in 8 real programs

Profiles: CPython 3.12, `cProfile` own (`tottime`) over 300 runs of each program's `main`
(module import excluded; the corpus `in2` input for the stdin programs). Times are the
profile's own seconds for those 300 runs; only the program's own functions are listed.

| program | hot function (own time) | typed path | first reason / action |
| --- | --- | --- | --- |
| `dev/t030.py` | `main` (0.002), `<genexpr>` (0.005) | no | `(int(x) for x in data[1:1 + n]) cannot be walked inline here; bind it to a name first: part = (int(x) for x in data[1:1 + n]) then walk part (for x in part: ...)` (the default build takes the general path with the same reason). Follow-up: an inline generator expression passed directly to `sorted()` needs a new lowering; the hot `main` and `<genexpr>` are not typed. |
| `gdev/g00_038.py` | `main` (0.001), `find_all_occurrences` | yes, whole program | already typed |
| `gdev/g10_036.py` | `dfs` (0.002), `all_vertices` (0.001), `find_hamiltonian_path` | no | `'GRAPH' is a module-level dict that a function cannot read: a module-level table must be a non-empty literal whose keys are all ints, all strs or all bytes (or tuples of ints / strs) and whose values are all one kind ...`. Follow-up: a module table whose values are `list[int]` (and the `Optional[List[int]]` result after it) is a new table/optional-list feature. |
| `corpus/.../t078.py` | `format_codepoint` (0.001), `main` (0.001) | no | `ord(); crossing between a str and a code point number is not built` for the `str` parameter. After that `main` also needs `next((...), "")`. Follow-up: `ord` on a non-proven one-code-point str needs TypedPath `TypeError`; `next(generator, default)` is not built. |
| `dev/t128.py` | `main` (0.014) | yes, whole program | already typed |
| `gdev/g11_012.py` | `step` (0.024), `render` (0.002), `<genexpr>` (0.011) | yes, whole program | already typed |
| `gdev/g14_016.py` | `person_from_dict` (0.002), `_require` (0.001), `deserialize_person` (0.001) | no (neither path builds) | `json.loads(s): the type of the result is not declared here ... (the general path could not build this program either); general path: isinstance() against an unknown type expected`. Follow-up: typed `json.loads` with a declared result type is a new feature. |
| `gdev/g11_018.py` | `simulate_random_walk` (0.106) | no → **yes**, whole program | `tuple assignment from Subscript ...` because the tuple pass did not know `random.choice(moves)` answers an element of `moves`. Fixed: `tuplib`/`tupcalls` now type `random.choice` (also `from random import choice`) as the list's element type, so `dx, dy = random.choice(moves)` lowers to field reads. |

The default (typed-first) build now takes the typed path for `g11_018.py` and prints CPython's
output; the other four general-path programs (`t030`, `g10`, `t078`, `g14`) keep their recorded
follow-ups.
