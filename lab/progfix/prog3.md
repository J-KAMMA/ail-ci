# prog3: typed reach of the hot functions (2026-11-01)

Method: each program was profiled with CPython 3.12 `cProfile` (own time). For the seven short
programs one process is dominated by imports, so `main()` was called repeatedly after the import
(300 / 3000 / 1000 / 3000 / 500 / 3 / 2000 times respectively) and the table below is the own-time
share of the program's own functions. `g12_008` is long enough to profile a single run (the table
still uses the same `simulate_mm1` share). Functions are listed in own-time order until they cover
80% of the program's own function time.

| program | hot functions (own-time share) | typed path? | first reason / fix |
| --- | --- | --- | --- |
| `g25_032` | `_transition` 33%, `step` 23%, `run` 11%, `run_scenario` 11%, `is_terminal` 8% | no | `'_ail_en_State_all' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant.` (enum members in a module-level table) |
| `g14_032` | `main` 58%, `format_timedelta` 22%, `build_events` 7% | no | `import of 'datetime' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |
| `g16_000` | `main` 73%, `fibonacci` 27% | no | `yield: this language has no generators.` |
| `g21_022` | `main` 35%, `build_nested_data` 27%, `sha256_hex` 22.5% (and `serialize_sorted` by cumulative time: 0.012 s in `json.dumps`) | no | `json.dumps of data: the type of this value is not known here -- bind it to a variable with a type annotation (...) ; built: int, float, str, bool, None, list[T], list[list[T]], dict[str, T] and dict[int, T] (T int / float / str) and literal dicts / lists of those` |
| `g09_008` | `longest_strictly_increasing_length` 92% | yes | already typed (whole program) |
| `g10_028` | `neighbors` 93% | no | ``only a struct type can be None: write `Node | None``` (`list[str] | None` return of `find_ladder`) |
| `g12_008` | `simulate_mm1` 100% of the program's own time; `random.expovariate` is the other hot callee (0.120 s of 0.319 s) | yes, after this fix | was `random.expovariate is not built; random is built for seed(<int>), random, randint, randrange, uniform, gauss, normalvariate, getrandbits, choice (a list), shuffle (a list) and sample (a list): CPython 3.12's MT19937, bit for bit` |
| `t370` | `main` 100% | yes | already typed (whole program) |

## Fix applied

`random.expovariate(lambd=1.0)` is now built on the typed path. `cruntime.py` adds
`ail_rand_expovariate` (`-log(1 - random()) / lambd`, with CPython's
`ZeroDivisionError: float division by zero` for `lambd == 0.0`, including `-0.0`; a negative
`lambd` returns the negative values CPython does). `stdlib3.py` lowers the call with the default,
positional and `lambd=` forms, and `pyfunc.py` registers the helper in `_AIL_RAND`. `g12_008` now
builds with `AIL_NO_GENERAL=1` and matches CPython byte for byte, so `simulate_mm1` (and the hot
`random.expovariate` calls inside it) run typed.

The generated C of all ten `lab/compare/src/*/main.ail` tasks is byte-identical before and after
(10/10 `program.c` same SHA-256).

## Follow-ups (large new features, left in place)

* `g25_032`: module-level tables of enum/struct members. Exact message:
  `'_ail_en_State_all' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant.`
* `g14_032`: a typed `datetime` module. Exact message:
  `import of 'datetime' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).`
* `g16_000`: generators (`yield`). Exact message:
  `yield: this language has no generators.`
* `g21_022`: a `json.dumps` of a heterogeneous nested `dict[str, Any]` / list of dicts. Exact message:
  `json.dumps of data: the type of this value is not known here -- bind it to a variable with a type annotation (`xs: list[int] = ...`) or use a literal; built: int, float, str, bool, None, list[T], list[list[T]], dict[str, T] and dict[int, T] (T int / float / str) and literal dicts / lists of those`
* `g10_028`: an optional list (`list[str] | None`) return type. Exact message:
  ``only a struct type can be None: write `Node | None```

`g09_008` and `t370` already build on the typed path; they need no change.
