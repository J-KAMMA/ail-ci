# prog18: hot functions of eight real programs on the typed path

Date: 2026-11-04.  CPython 3.12 with cProfile, own time (`tottime`) among the program's own
functions, on the largest published input (`lab/corpus/tasks/tNNN/in2.txt` for the corpus
programs; the census programs take no input).  The profiler compiles each module once and then
executes it with fresh `__main__` globals per repetition (500 reps; 2000-3000 for the cheap
programs), so import/compile time is outside the profile.  Programs were not edited.

"Typed" means the default build takes the typed path (`ail_chatgpt.py compile`, no "built on the
general path" note) -- or, for a function inside a general-path program, that mixed mode emits a
typed clone for it (`typed_inline`).  The six programs that build typed are whole-program typed,
so every function in the 80% set is typed.

## Profile (functions holding 80% of the program's own time)

| program | functions by own time (share) |
|---|---|
| `t391.py` | `main` 97.2% |
| `t443.py` | `format_groups` 77.6%, `first_letter` 14.6% (92.2%) |
| `t198.py` | `main` 84.0% |
| `t219.py` | `main` 93.1% |
| `t210.py` | `main` 68.2%, `<genexpr>` 28.8% (97.0%) |
| `g11_014.py` | `multi_source_bfs` 53.7%, `<genexpr>` 33.3% (87.0%) |
| `g02_038.py` | `pascal_binomial` 99.4% |
| `g19_014.py` | `main` 47.6%, `<module>` 40.5% (88.1%) |

## Result per hot function

`t443`, `t198`, `t210` and `g02_038` were already whole-program typed before this batch (the CLI's
Python-surface pass lowers their `typing` imports and annotations; a direct `pyfunc.to_c` on the
raw source does not).  `g02_038` computes C(100, 50), which leaves int64: the typed build stops
loudly at the int64 boundary (declared 64-bit semantics, corpus class `overflow`) where CPython
prints the exact big int, so it is not a same-output program under the default build.

| program | hot function(s) | typed before? | first refusal before | after |
|---|---|---|---|---|
| `t391` | `main` | no | `Random.randrange must take plain positional arguments, no defaults, *args or **kwargs` (the typed random prelude's `randrange`; the same for `choices`, `triangular`, `gauss`, `normalvariate`, `expovariate`) | still no: after methods with optional parameters the prelude's `__init__` needs `mt = self.mt` (two references to one list) and a list field `Random.mt`; a larger feature (follow-up) |
| `t443` | `format_groups`, `first_letter` | yes | none | unchanged, still typed |
| `t198` | `main` | yes | none | unchanged, still typed |
| `t219` | `main` | no | `'visited' is declared ('olist', '_AilT_i_i'); assigning int is unsupported` (line 12, `visited: list[tuple[int, int]] = [(x, y)]`) -- and, after that statement, the typed entry was a generated helper: `the entry function cannot return checked str` | **yes, whole program typed** |
| `t210` | `main`, `<genexpr>` | yes | none | unchanged, still typed |
| `g11_014` | `multi_source_bfs`, `<genexpr>` | no | `max() with keyword arguments is not built` (line 36, `max((max(row) for row in dist), default=0)`) | **yes, whole program typed** (then `a nested format spec ({x:{w}})` for `f"{v:>{width}}"`) |
| `g02_038` | `pascal_binomial` | yes | none | unchanged, still typed (int64 overflow at `math.comb(100, 50)`, declared) |
| `g19_014` | `main`, `<module>` | no | `import of 'datetime' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json)` | still no: `timedelta` is a stdlib class the typed path does not model (follow-up) |

Result: 6 of the 8 programs are whole-program typed after the batch (4 before).  Of the 11 hot
functions/units in the 80% sets, 9 are typed after the batch (6 before).

## Compiler changes (`AIL_CURRENT/python/pkg-v12/pyfunc.py`)

1. `_script_entry` searched only top-level expression statements for the call a Python script makes
   at module level.  A script ending with the usual
   `if __name__ == '__main__': main()` guard, whose generated repr/deque helpers are appended
   after the script, therefore found no entry: `fns[-1]` stayed a helper that returns a checked
   str, and the typed path refused with `the entry function cannot return checked str` (no
   position).  The guard's body (and its `else` arm) is searched too; `t219` and `g11_014` both
   start at this refusal after their earlier reasons are removed.

2. `_numeric_expression_needed` returned true for any expression containing a numeric local, so
   `_numeric_assign` treated a container literal that names numeric locals as a numeric binding
   and declared the target as an int:
   `visited: list[tuple[int, int]] = [(x, y)]` (after the repr helper turns the tuple into a
   class) failed with `'visited' is declared ('olist', '_AilT_i_i'); assigning int is
   unsupported`.  A list/tuple/set/dict display or comprehension is never a numeric binding; the
   declaration now keeps its declared kind.

3. `max(xs, default=d)` / `min(xs, default=d)` were refused (`max() with keyword arguments is not
   built`).  The fold accumulator now starts at `d` (evaluated before the walk, as CPython
   evaluates the argument list before iterating), so an empty walk returns `d` and a non-empty one
   overwrites it.  Built for the numeric walk, the list-of-instances walk and the list-of-lists
   walk; `d` must be the same kind as the elements (int or float).  A str fold, a pair fold and a
   `default` of another kind are refused by name.

4. `f"{v:>{width}}"`: the format-spec width may now be a field.  The literal part before it is
   parsed at compile time (fill/alignment only) and the part after it (grouping, precision, type);
   the width expression must be an int and is passed to the existing `int64_t` width argument of
   `ail_fmt_spec_int` / `ail_fmt_spec_float` / `ail_fmt_spec_str` / `ail_fmt_gen` /
   `ail_fmt_gen_str`.  A negative width is CPython's sign option, not a padding request:
   `format(9, '>-5')` is `'    9'`, so int/float use `abs(w)`, while a str raises the same
   `ValueError("Sign not allowed in string format specifier")`.  A prefix with a sign, `#`, the
   `0` flag or a width, and a non-int width, are refused by name.

The generated C of the ten `lab/compare` tasks is byte-identical to the base commit (16 builds
with C, compared with `--debug-dir`; the four `main.py` variants that the general path already
refuses fail with the same message and emit no C).

## Review fixes (bool is not an int here)

A bool is an `int64_t` 0/1 in C, so `_etype()` says INT for it -- but CPython does not treat it as
an int in either of the two new places:

5. `_fmt_width_c` now also refuses a bool width: `f"{9:>{flag}}"` with `flag: bool` was rendered
   as `[9]` on the default build, where CPython raises
   `ValueError: Invalid format specifier '>True' for object of type 'int'`.  The refusal is
   `the nested format-spec field has to be an int (it stands for the width); got bool` (the same
   through a parameter or an attribute).

6. Both `max`/`min` default folds now refuse a bool default: `max(xs, default=True)` was folded to
   `1` (and `min(..., default=False)` to `0`) on the default build, where CPython returns the bool
   itself and prints `True`/`False`.  The refusal is
   `max()/min() with default= of bool where the elements are an int; only a default of the same
   kind is built`.  `_is_bool_expr` (boolkind.py) is the test in both places.


## Following up (not fixed here)

- `t391`: methods with optional parameters (`Random.randrange(self, start, stop=None, step=1)` and
  five more prelude methods: `Random.randrange must take plain positional arguments, no defaults,
  *args or **kwargs`), then `mt = self.mt` (`makes a second reference to the same container`), a
  list field (`'Random' has no field 'mt'`) and `subscripting Attribute`.  This is a
  `random.Random` instance feature, larger than this batch.
- `g19_014`: `import of 'datetime' is not available`; `timedelta` values and
  `timedelta.total_seconds()` need a new stdlib module on the typed path.
