# prog9: the hot functions of eight real programs on the typed path

CPython 3.12, `cProfile -s tottime`. The hard-coded `gdev` programs finish in under a millisecond
(the profiler's own import overhead is most of the report), so for those the table names the whole
algorithm's single hot function; the other four were profiled on the largest public task input (or
a scaled input of the same shape for `t254`/`t208`/`t308`/`t216`).

| program | hot functions by own time | ~80% set |
| --- | --- | --- |
| `t254.py` | `main` 0.009 s, `str.split` 0.004, `<module>` 0.002, `<genexpr>` 0.001, `sum` 0.001 | `main` (+ its generator expression) |
| `g09_002.py` | `lcs_length` (the only program function; 190 `max` calls) | `lcs_length` |
| `t208.py` | `tokenize` 0.118, `parse_factor` 0.042, `str.isdigit` 0.029, `parse_term` 0.026, `peek` 0.025, `str.isspace` 0.017, `parse_expr` 0.016, `main` 0.013, `advance` 0.012 | `tokenize`, `parse_factor`, `parse_term`, `peek`, `parse_expr`, `main`, `advance` (0.252 of 0.357 s) |
| `g23_026.py` | `find_extremes`, `main` | `find_extremes` |
| `g18_006.py` | `find_zero_sum_triples` (the comprehension), `main` | `find_zero_sum_triples` |
| `g17_022.py` | `flatten`, the `map`/`filter` lambdas | `flatten` + its lambdas |
| `t308.py` | `longest_common_substring` 0.370 s, `main` 0.000 | `longest_common_substring` (99%) |
| `t216.py` | `main` 0.106 s | `main` (97%) |

## Status and first reason

"before" is the first refusal on the typed path at the start of this job. "after" is the state at
the end. `mixed mode` here means a typed function may call a general one; the programs themselves
were never edited.

| program | hot set typed before | first reason before | after this job |
| --- | --- | --- | --- |
| `t254.py` | yes (whole program) | -- | still typed |
| `g09_002.py` | yes (whole program) | -- | still typed |
| `t208.py` | no (all `Parser` methods + `main` general) | `while self.peek() in ('+', '-')`: `passing a number where _ail_in_1() wants a str` (the Optional `peek()` was not lowered at all) | the Optional `in`, Optional `while` test and method row unpack now build, but `Parser.parse()` / `parse_expr()` / `parse_term()` / `parse_factor()` return `int | float`, which has no single C representation. The program stays general and matches CPython. |
| `g23_026.py` | yes (whole program) | -- | still typed |
| `g18_006.py` | no (`find_zero_sum_triples`) | `the entry function cannot return checked str`; the underlying blocker, once that shape is fixed, is `t holds a tuple in CPython; here it is a list, and this use of it (print, ==, a dict key, a slice...) would differ. Index it, loop over it, or unpack the tuple into names in the for statement` | unchanged: a tuple value out of `itertools.combinations` is a new feature (follow-up) |
| `g17_022.py` | no (`flatten` + lambdas) | `'nested' is annotated list[Any], which this compiler has no rule for.` | unchanged: `list[Any]` / recursive `map`+`filter` is a new feature (follow-up) |
| `t308.py` | yes (whole program) | -- | still typed |
| `t216.py` | no (`main`) | `'counts' is a sdict; only an array, a list, a list of floats, a set, a dict, bytes and a list of str are walked as flat sequences here.` | `main` is typed: `sorted(Counter)` sorts the keys and `repr(dict)` / `print(dict)` / `f"{d}"` build CPython's dict repr |

## Compiler changes

* `optlib.py`: `in` / `not in` of a scalar Optional against a literal tuple/list/set with no
  `None` element becomes `flag and value in literal` (`not (...)` for `not in`); an Optional call
  in a `while` test becomes `while True:` with the call and inverted test at the top of the body;
  a method returning an Optional scalar is recognised as such (`self.peek()`), including when the
  method is called from another method. Options are still lowered only when the whole function
  can be lowered; otherwise the source is left as written.
* `pyfunc.py`: `a, b = p.method()` unpacks a method's small per-field row return (SROW), the same
  ABI a plain function's tuple return already used; a `bool` field in that row keeps its
  `True`/`False` printing. A row's str field is handed to the caller as an owned copy
  (`ail_str_return_owned` then `ail_str_adopt`), so the callee's arena can be freed safely.
* `pyfunc.py`: `sorted(d)` for a typed `dict[str, int]` / `Counter[str]` copies each key's text
  into the function's str arena, pushes those owned copies into an `ail_slist` and sorts them,
  exactly as `sorted(list[str])` already did; it works for a local and for a dict parameter, and
  the result stays valid after the source dict is mutated (`del`, `clear`) or goes out of scope.
* `pyfunc.py` + `cruntime.py` (`DICTTEXT`): `print(d)`, `repr(d)` and `f"{d}"` of a str-keyed int
  dict, annotated (`dict[str, int]`, `Counter[str]`) or unannotated, in CPython's insertion order,
  keys quoted by the existing `ail_fmt_repr_str` (quotes, escapes, non-ASCII), values decimal.
  The runtime block is selected only by a program that asks for this text.
* `pyfunc.py`: a return annotation that is exactly `int | float` is now refused by name instead
  of being inferred as `float` (which printed `3.0` where CPython prints `3`). This keeps `t208`
  on the correct general path.

## Follow-ups (big new features, exact messages)

* `t208`: `Parser__parse() returns \`int | float\`; a union of int and float is not built (its
  two C representations differ). Split it into an int function and a float function, or return
  float and convert the int result caller-side`
  (a typed int/float tagged numeric return would let the rest of the `Parser` methods build too).
* `g18_006`: the first strict refusal is `the entry function cannot return checked str` (both
  base and this branch); with that shape fixed, the tuple message is `t holds a tuple in CPython;
  here it is a list, and this use of it (print, ==, a dict key, a slice...) would differ. Index
  it, loop over it, or unpack the tuple into names in the for statement` (a tuple value from
  `itertools.combinations`; the pool stream only unpacks into names today).
* `g17_022`: `'nested' is annotated list[Any], which this compiler has no rule for.` plus
  `unsupported local annotation list[Any].` (recursive `list[Any]` with `map`/`filter` lambdas;
  a heterogeneous container type would be needed).

## Verification

`test_ail_prog9.py` builds the six typed programs with `--strict` and compares them with CPython on
the public inputs plus empty/whitespace/negative/non-ASCII/error boundaries; it also compares
`t208` on the default (general) build and checks the `int | float` refusal. It also covers
`sorted(d)` after `del`/`clear`, returning it from a function whose dict is local, a dict
parameter, an empty dict, a reverse sort and non-ASCII/empty keys. The line-by-line probes in
`/tmp/probes` (`p_opt_in`, `p_opt_in_route`, `p_dict_sorted_edge`, `p_dict_repr_routes`,
`p_dictrepr`, `p_dictun`, `p_methpair`, `p_sort_del`, `p_sort_clear`, `p_sort_return`,
`p_sort_all`) all match CPython on both `cmp.sh` builds. The generated C of the ten `lab/compare`
`main.ail` tasks is byte-identical to `HEAD` (all ten emit C), and the ten `main.py` builds also
match: five emit C byte-identically and five refuse with the same message (only the absolute source
path differs).
