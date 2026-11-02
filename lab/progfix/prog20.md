# prog20: hot functions of eight real programs

Date: 2026-11-02.  CPython 3.12.3, cProfile, gcc on the GitHub runner.  Programs were not edited.
The profiler harness compiles the module once, then executes it with fresh `__main__` globals on
every repetition, so import/compile time is outside the profile.  The table reports own time among
that program's own functions; `<module>` is the top-level code.

## Profile

| program | input | reps | functions by own time (share) |
|---|---|---:|---|
| `g03_012.py` | none | 1000 | `main` 43.2%, `<module>` 32.7%, `validate_positive` 11.5% (87.4% together) |
| `g03_028.py` | none | 1000 | `main` 40.3%, `<genexpr>` 24.9%, `<module>` 20.8% (86.0%) |
| `g05_006.py` | none | 1000 | `main` 35.7%, `<lambda>` 34.6%, `<module>` 20.5% (90.8%) |
| `g18_002.py` | none | 1000 | `main` 43.6%, `<lambda>` 27.8%, `<module>` 24.7% (96.1%) |
| `t284.py` | `in2.txt` | 2000 | `main` 49.9%, `find` 21.6%, `union` 10.9% (82.4%) |
| `t206.py` | `in2.txt` | 2000 | `main` 98.0% |
| `g25_002.py` | none | 1000 | `insert_coin` 25.2%, `_transition` 22.1%, `main` 21.3%, `<module>` 13.0% (81.6%) |
| `g14_012.py` | none | 1000 | `main` 41.5%, `<module>` 25.5%, `Rectangle` 12.9%, `Account` 11.8% (91.7%) |

## Result per hot function

"Before" is the tree at the start of the batch (`git archive HEAD`); "after" is this branch.
`t206` was already whole-program typed.  The other five programs remain on the general path for
the named reasons below; none of those was edited.

| program | hot function(s) | typed before? | first refusal before | after |
|---|---|---|---|---|
| `g03_012` | `main`, `validate_positive` | no | `statistics.geometric_mean used here is not built (mean, fmean, ... are, over a list of int)` (line 36) | still no: adding `geometric_mean`/`harmonic_mean` is only the first step; `is_at_least` then returns a non-bool from `a >= b or math.isclose(...)`, and `data = list(DATA)` is a list-of-int store of floats |
| `g03_028` | `main`, `<genexpr>` | no | `dunder method Fraction.__float__; only __init__ is supported here, no other dunder (...)` (line 237) | still no: the `fractions.Fraction` class needs its arithmetic/comparison dunders; the general path builds it |
| `g05_006` | `main`, `<lambda>` | no | `a tuple used where a single value is needed. write instead: unpack it into names ...` (line 9, the tuple key of `min`) | **yes, whole program typed**: the dict/sequence tuple-key lowering compares the fields lexicographically and keeps the first tie |
| `g18_002` | `main`, `<lambda>` | no | `class enumerate needs two distinct (index, element) names` (line 17) | **yes, whole program typed**: `for rank, (word, count) in enumerate(top, start=1)` reads each tuple field once per iteration |
| `t284` | `main` | no | `call to iter(); this compiler builds only the builtins it names` (line 31) | still no: after an `iter()` lowering the next blockers are the generator expression in `sorted(v for v in range(n) if ...)` and `" ".join(map(str, sizes))` |
| `t284` | `find`, `union` | no in the program (class methods are not mixed-mode candidates); the `UnionFind` class compiles typed when cut out | the enclosing `main` refusal above sends the whole program to the general path | still no in the program; needs the `main` iterator/generator/`join(map(...))` work |
| `t206` | `main` | yes | none | unchanged, still typed |
| `g25_002` | `insert_coin`, `_transition`, `main` | no | `'_ail_en_State_all' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant` (line 222) | still no: a typed `Enum`/`auto()` module table and the `@dataclass` methods are a larger feature |
| `g14_012` | `main`, `Rectangle`, `Account` | no | `class attribute Rectangle.area = field(init=False); a class attribute here is an int, float, str or bool literal` (line 10), and `an InitVar in a @dataclass is not built` | still no: `field(init=False)` and `InitVar` in a dataclass are follow-ups; the general path refuses this program too |

## Compiler changes

- `AIL_CURRENT/python/pkg-v12/iterlower.py`: `min`/`max` with a tuple-returning key
  (`lambda city: (-pops[city], city)`) now compares the fields lexicographically instead of
  building a tuple after the tuple-lowering pass.  The fields are evaluated once per element in
  Python order, comparison short-circuits at the first unequal field, and the first element wins a
  tie.  A dict source is walked without copying its keys into an untyped empty list; a sequence
  source (list, range, slice) uses the existing count/index walk.  `default=` is unchanged.
- `AIL_CURRENT/python/pkg-v12/pyfunc.py`: `enumerate(source, start)` accepts a nested tuple target
  for a list of tuple instances (`for i, (word, count) in enumerate(top, start=1)`).  Each field is
  materialised into a correctly typed local once per iteration; the index is `start + position`,
  the start is evaluated once (after the iterable), and the position is private, so rebinding the
  index or the start variable inside the body cannot change the next step.  The same shape over a
  named `list[tuple[str, int]]` row list (`ctx.srowtypes`) is handled by the parallel branch in
  `_for_enumerate_start`.

## Following up (not fixed here)

The five programs left untyped need a larger feature, with these exact first messages:

- `g03_012`: `statistics.geometric_mean used here is not built (...)`; then
  `the result of is_at_least() is declared bool, but ... is not a bool`; then
  `a list holds integers; appending a float would truncate it`.
- `g03_028`: `dunder method Fraction.__float__; only __init__ is supported here, no other dunder ...`.
- `t284`: `call to iter(); this compiler builds only the builtins it names`; then
  ``(v for v in range(n) if uf.find(v) == root0)`` `cannot be walked inline here`; then
  `.join() on a str takes one list[str]` (the `map(str, ...)` source).
- `g25_002`: `'_ail_en_State_all' is a module-level list of non-numbers ...`.
- `g14_012`: `class attribute Rectangle.area = field(init=False) ...` and
  `an InitVar in a @dataclass is not built`.

Result: 3 of the 8 programs are whole-program typed after the batch (`g05_006`, `g18_002`,
`t206`), against 1 before (`t206`).  Of the 18 hot functions in the 80% sets, 5 are typed after
the batch against 1 before.
