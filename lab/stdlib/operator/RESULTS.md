# `operator`: 12 real programs against CPython

Each program was built with the default command

    python3 AIL_CURRENT/ail_chatgpt.py compile <program>.py --syntax python -o <program>

and run next to `python3 <program>.py`.  "Initial" is the tree at the start of the job
(`ab13923`), "final" is this branch.  Both the default build and the forced general build
(`AIL_UNIFIED_FORCE=1`) were run for every program that builds; the 11 that build print the same
stdout and exit code as CPython.

| program | initial | first refusal message | final |
| --- | --- | --- | --- |
| `sort_records.py` | refused | `not in the subset: key= must be a lambda or a function name (the general path could not build this program either); general path: a key=/map() argument that is not a lambda, a one-argument def, or one of int/float/str/abs/len` | typed |
| `object_attrs.py` | refused | `not in the subset: key= must be a lambda or a function name (the general path could not build this program either); general path: a key=/map() argument that is not a lambda, a one-argument def, or one of int/float/str/abs/len` | typed |
| `method_pipeline.py` | refused | `not in the subset: key= must be a lambda or a function name (the general path could not build this program either); general path: a key=/map() argument that is not a lambda, a one-argument def, or one of int/float/str/abs/len` | typed |
| `mutate_map.py` | refused | `p.ail:1:1: not in the subset: operator.setitem() with these arguments is not built (see the note below)` | typed |
| `sequence_scan.py` | refused | `p.ail:1:1: not in the subset: operator.contains() with these arguments is not built (see the note below)` | typed |
| `truthy_values.py` | refused | `p.ail:1:1: not in the subset: operator.truth() with these arguments is not built (see the note below)` | typed |
| `arithmetic_ops.py` | typed | -- | typed |
| `comparison_dispatch.py` | typed | -- | typed |
| `functional_pipeline.py` | typed | -- | typed |
| `inventory_report.py` | refused | `p.ail:2:1: not in the subset: operator.contains() with these arguments is not built (see the note below)` | typed |
| `bitmask_flags.py` | refused | `p.ail:1:1: not in the subset: operator.truth() with these arguments is not built (see the note below)` | typed |
| `sequence_concat.py` | refused | `p.ail:1:1: not in the subset: operator.iadd() with these arguments is not built (see the note below)` | refused |

Initial score: 3/12 build.  Final score: 11/12 build, all 11 match CPython's stdout and exit code.

## What was fixed (ail_syntax.py)

The Python surface already lowered `operator.add/sub/mul/truediv/floordiv/mod/pow/and_/or_/xor/
lshift/rshift`, the comparisons, `neg/pos/invert/not_/abs/getitem`, and `itemgetter(k)`.  This job
adds, as rewrites of the same call (never of the program):

* `itemgetter(k, j, ...)` and `itemgetter(k)` as a value, lowered to a one-argument lambda whose
  body is the subscript or tuple of subscripts (`itemgetter()` itself is refused, as CPython raises
  `TypeError: itemgetter expected 1 argument, got 0`).
* `attrgetter("a", "b.c")` as a key or a value, lowered to a lambda over attribute reads.
* `methodcaller("name", args..., kwargs...)` as a key or a value, lowered to a lambda calling the
  method (the method name must be a string literal identifier).
* `setitem` / `delitem`, lowered to small prelude helpers that perform `o[k] = v` / `del o[k]` so
  the container is mutated (and KeyError / IndexError are CPython's).
* `contains` -> `b in a`; `countOf` / `indexOf` -> prelude helpers that iterate the sequence and
  compare each element.  This is CPython's `PySequence_Count` / `PySequence_Index`, not
  `str.count` / `str.index`: `countOf("banana", "na")` is 0 and `indexOf("abc", "bc")` raises
  `ValueError: sequence.index(x): x not in sequence`, which the programs and probes check.
* `truth` -> `bool(a)`, `is_` / `is_not` -> `is` / `is not` (identity on numbers keeps the existing
  named refusal, so these are used on `None` and objects).

## Follow-up (out of scope here)

`sequence_concat.py` still uses the in-place operator functions and the sequence helpers.  It is
refused by name with:

    p.ail:1:1: not in the subset: operator.iadd() with these arguments is not built (see the note below)
    note: p.ail:14: operator.concat() with these arguments is not built; operator.add/sub/mul/truediv/floordiv/mod/pow/and_/or_/xor/lshift/rshift, the comparisons, neg/pos/invert/not_/abs/getitem/contains/countOf/indexOf/truth/is_/is_not called directly, setitem/delitem, and itemgetter/attrgetter/methodcaller (as a key= or a value) are built
    note: p.ail:15: operator.concat() with these arguments is not built; ...
    note: p.ail:16: operator.length_hint() with these arguments is not built; ...
    note: p.ail:17: operator.index() with these arguments is not built; ...
    note: p.ail:20: operator.iadd() with these arguments is not built; ...

`concat`, `length_hint`, `index` and the `i*` in-place family need their own sequence/mutation
lowering (CPython's `concat` has per-type TypeError text and `iadd` must mutate a list but rebind an
int), so they are left as a named follow-up rather than guessed at.

## Generated C

The generated C of the 10 `lab/compare/src` tasks (both `main.ail` and the `main.py` variants that
build) was captured before and after this change with `--debug-dir`; every captured `program.c` is
byte-identical.  None of those programs imports `operator`.
