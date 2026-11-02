# Typed reach, batch 2: eight real programs (2026-11-01)

Profiled with CPython 3.12.3, `python3 -m cProfile -s tottime`. The stdin programs used a generated
input of 200,000 items (`t261`, `t315`, `t408`) or 50,000 lines (`t079`). The four fixed-input
`lab/census/gdev` programs were run through `main()` 2,000 times (`g11`, `g20`), 3,000 (`g22`) or
500 (`g17`) so their own times are measurable. Own times below are milliseconds; the hot set is the
user-written functions that together hold about 80% of the program's own time (builtins such as
`print`, `max`, `re.findall` and the `ipaddress` library are not candidates for the typed path).

## Hot functions and the typed path

| Program | Hot function(s) (own time) | Typed before | First reason before | After this job |
| --- | --- | --- | --- | --- |
| `t261` | `main` 122, `polygon_perimeter` 43, `polygon_area` 32 | no / no | `unresolved-param points` (`list[tuple[int, int]]`: the mixed-mode vocabulary has no tuple-list/row ABI) | same, follow-up |
| `t408` | `main` 226, `state_at` 63 | `state_at` yes (candidate) | hybrid only: `division or power can raise` for `t % 8` | **`state_at` accelerated** by the hybrid |
| `g11_008` | `sub_grid_sums` 32, `format_grid` 2 + its genexprs 28 | no / no | `unresolved-param matrix`, `unresolved-param grid` (`List[List[int]]` / nested list) | same, follow-up |
| `g22_030` | `solve_tsp` 83, `main` 5 | no | `unresolved-param dist` (`List[List[int]]` / nested list) | same, follow-up |
| `g20_024` | `count_target_words` 5 (+ builtin `re.findall` 16) | no | `unresolved-param targets` (`list[str]`); the result `dict[str, int]` has no mixed-mode ABI either | same, follow-up |
| `t315` | `max_non_adjacent_sum` 39 (+ builtin `max` 60), `main` 32 | no | `unresolved-return` (the return expression mixes an untyped `None` branch) | now reaches `to_c`, stopped by the next reason below |
| `t079` | `distinct_char_count` 59, `reverse_words` 21, `main` 12 | no / no | `unresolved-param line` for `reverse_words` / `to_c-refused` (inline set comprehension) for `distinct_char_count` | **`reverse_words` accelerated** by the hybrid; `distinct_char_count` follow-up |
| `g17_020` | `ipv4_sort_key` 6 + its genexpr 5, `main` 3 (+ `ipaddress` library) | no / no | `unresolved-param address` (the `tuple[int, int, int, int]` result has no mixed-mode ABI either) / `unresolved-param addresses, key` (`list[str]` + `Callable`) | same, follow-up |

`main` is not a target: its input/output and `-> None` keep it general in every program, and the
accelerated helpers are what the programs spend their time in.

## Fixed here

1. **Return kinds are proved from the body, never filled from an annotation** (`pymix`). CPython
   does not enforce annotations, so `def isup(line: str) -> int: return line.isupper()` really
   returns a bool; trusting `-> int` boxed it as an int on the raw build path. `_expr_kind` now
   knows the fixed result kind of the str methods (`isupper`/`split`/`join`/...), `list`/`sorted`,
   `abs`/`ord`/`chr`, and `sys.stdin.read()`/`readline()`, so the kind comes from the expression.
   `t079.reverse_words` (`return " ".join(reversed(line.split()))`) is a str proof, and the module's
   `text = sys.stdin.read()` / `lines = text.splitlines()` chain resolves `line` without an
   annotation.
2. **The hybrid allows `/`, `//`, `%` by a literal nonzero constant, signed included**
   (`ail_cpython_hybrid._unsafe_body`). Such an operation cannot raise `ZeroDivisionError`, so
   `t408.state_at` (`t % 8`) and `// -3` are now wrapped and accelerated. A variable divisor still
   keeps the function in CPython.
3. **The hybrid allows a call it can prove pure and non-raising** (`_safe_call`): a str method whose
   receiver is provably str and whose arguments are the exact literal types CPython requires
   (`split`, `join`, `strip`, `replace`, `find`, `count`, `startswith`, ...), and `len`,
   `reversed` over a proved str/list sequence. That is what makes `t079.reverse_words`, a hot
   helper of that program, accelerated; `print`, `int()`, `.index()`, a bytes result and
   any user call still keep their function in CPython.
4. **`pymix` agrees on signed literal divisors** (`_provably_nonzero` now reads a unary sign).
   Without this, `t // -3` still counted as a possible `ZeroDivisionError`, so the same helper
   was refused as `exception-capable` whenever the program used it as a value or under a
   `try/except`; the typed and hybrid passes now classify it the same way.

## Follow-ups (left, with the compiler's exact message)

* Nested list / tuple-list parameters (5 hot helpers: `t261` twice, `g11` twice, `g22`):
  `unresolved-param points`, `unresolved-param matrix`, `unresolved-param dist`. The mixed-mode
  kind vocabulary is `int`, `float`, `bool`, `str`, `list[int]`, `list[float]`, `list[str]`; its ABI
  has no row/nested-list form. Directly asking `to_c` for `List[List[int]]` says:
  `'matrix' is annotated List[List[int]], which this compiler has no rule for.`
* `list[str]` parameters and `dict` / tuple / `list[str]` results (`g20`, `g17`):
  `unresolved-param targets`, `unresolved-param addresses, key`, `unresolved-return`. The mixed-mode
  ABI carries scalar results and only `list[int]`/`list[float]` parameters.
* A scalar `int | None` local (`t315`):
  `int | None: only a struct type can be None here (a scalar Optional is built as a parameter, a
  return type or a local of a plain function; a note below names the use that is not).`
* A set comprehension of `str` used as a value (still blocks `t079.distinct_char_count`):
  `` `{ch for ch in text if ch not in '\r\n'}` cannot be walked inline here; bind it to a name
  first: `let part = {ch for ch in text if ch not in '\r\n'};` then walk `part`
  (`for x in part { ... }`) ``. The eager set-comprehension fold exists only for integer elements.

## Verification

`AIL_CURRENT/test_ail_prog2.py` (registered in `tests.d`) checks the proof rules directly
(`reverse_words` ret `str`; `isup` ret `bool`, not the annotated `int`; an annotation alone does
not fill an unknown return; contradicting branches stay `unresolved-return`), builds the raw
`pyc.py --strict --file` path for `isup` and compares it with CPython, builds `reverse_words` on
the typed and general paths, and builds it plus the `t408` source with `ail build --cpython`:
`reverse_words`, `state_at` and the signed-literal `down` are accelerated, the variable-`%` helper
is not, and stdout/exit status match CPython on every input (including the caught
`ZeroDivisionError`).
