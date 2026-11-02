# prog27: typed reach of the hot functions of eight real programs

CPython 3.12.3, `cProfile` over repeated `main()` calls with the largest published input
(`lab/corpus/tasks/<t>/in2.txt`; 2,000 repeats, 1,000 for t176, 300 for g17_018) so the program's
own functions are measurable. Shares are of the program's own-function time; the hot set is taken in
own-time order until it covers 80%. The typed path is the default `compile --syntax python` build.
"Typed before" is per function: a helper can build on the typed path even while its caller is
blocked, which is what mixed mode can accelerate.

| program | hot function (own share) | typed before | typed now | first reason before / follow-up |
| --- | --- | ---: | ---: | --- |
| g05_026 | `build_histogram` 52.2% | no | **yes** | `build_histogram(): the default for 'symbol' must be a compile-time int, float or bool constant (a list, dict, str or None default is refused).` |
| g05_026 | `count_words_per_line` 30.7% | yes (helper alone) | **yes** | the helper already built; the whole program stopped at its caller |
| g05_026 | `main` 17.0% | no | **yes** | calls `build_histogram`, so it stopped at the same default |
| g07_016 | `main` 81.7% | no | no (follow-up) | `Slice is not one of the expression shapes this compiler builds; it is refused by name rather than guessed at (SEMANTICS.md section 5)` |
| g07_016 | `remove_all` 18.3% | no | no (follow-up) | same slice assignment; with that removed, `'items' is a list parameter, which is read-only here.` |
| t223 | `count_components` 95.8% | no | no (follow-up) | ``field `v` is a list or dict that gets bools and numbers (Python keeps each element's own type)`` |
| t223 | `main` 4.2% | no | no (follow-up) | calls `count_components`; next also `_AilDeque_tup2_int_int.buf has unsupported field type array; fields require a known nonnullable scalar, container or managed class type` |
| t176 | `<genexpr>` line 9 51.1% | no | no (follow-up) | `json.loads(s): the type of the result is not declared here; write the type down: 'data: dict[str, int] = json.loads(s)' (the types are int, float, str, bool, list[T], list[list[T]], dict[str, T])` |
| t176 | `main` 48.9% | no | no (follow-up) | same `json.loads` into `list[dict]` reason |
| t110 | `main` 100% | yes | yes | -- |
| g03_010 | `pearson_correlation` 60.8% | yes | yes | -- |
| g03_010 | `main` 23.2% | yes | yes | -- |
| g17_018 | `main` 40.0% | no | no (follow-up) | `duplicate AIL name: _ (\`def _\` / \`class _\` is bound a second time at module level; a function here has one definition, which also rules out the \`@f.register\` / \`def _(...)\` overload pattern)` |
| g17_018 | `_` line 22 7.8%, line 48 6.6%, line 98 5.2%, line 104 4.9% | no | no (follow-up) | same duplicated-registration name; `@describe.register` is not built |
| g17_018 | `<genexpr>` line 75 4.1%, `_` line 73 3.9%, `_` line 79 3.4%, `<genexpr>` line 81 2.4%, `_` line 85 2.3% | no | no (follow-up) | same program-level refusal (the hot set reaches 80.6% here) |
| t375 | `main` 100% | yes | yes | -- |

## Fixed here

`python/pkg-v12/pyfunc.py`: a parameter default may now be a compile-time `str` or `bytes` literal,
not only an int/float/bool constant. Both are immutable values the emitter already builds as
constants (`_expr`'s Constant path), and the call site fills an omitted argument from the same AST
node, so no new runtime path is involved. A literal whose kind does not match the settled parameter
kind is still refused by name (a str default for `int`/`bytes`, a bytes default for `str`, a float
default for `int`), and list/dict/None defaults keep their previous refusal. This removes the one
blocker of all three hot g05_026 functions; the program is now typed as a whole (both builds match
CPython).

The generated C of the ten `lab/compare/src/*/main.ail` tasks is byte-identical to the base commit
(all ten `to_c` SHA-256 values compared).

## Follow-ups (big new features, left by name)

* `lab/census/programs/gdev/g07_016.py`: full-slice assignment `items[:] = [...]` and, behind it,
  a mutable list parameter. Exact first message:
  `Slice is not one of the expression shapes this compiler builds; it is refused by name rather than guessed at (SEMANTICS.md section 5)`;
  after a slice lowering it would stop at `'items' is a list parameter, which is read-only here.`
* `lab/corpus/programs/glm-5.3-flash-free/t223.py`: nested `list[list[bool]]` storage and a deque of
  `(int, int)` tuples. Exact first message:
  ``field `v` is a list or dict that gets bools and numbers (Python keeps each element's own type)``;
  then `_AilDeque_tup2_int_int.buf has unsupported field type array; fields require a known nonnullable scalar, container or managed class type`.
* `lab/census/programs/dev/t176.py`: `json.loads` into a heterogeneous `list[dict]`. Exact first
  message:
  `json.loads(s): the type of the result is not declared here; write the type down: 'data: dict[str, int] = json.loads(s)' (the types are int, float, str, bool, list[T], list[list[T]], dict[str, T])`.
* `lab/census/programs/gdev/g17_018.py`: `functools.singledispatch` registration with repeated
  `def _` names. Exact first message:
  `duplicate AIL name: _ (\`def _\` / \`class _\` is bound a second time at module level; a function here has one definition, which also rules out the \`@f.register\` / \`def _(...)\` overload pattern)`.
