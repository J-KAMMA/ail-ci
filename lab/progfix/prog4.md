# Typed reach, batch 4

`cProfile` own time under CPython 3.12.3, aggregated over `in0`/`in1`/`in2` where the task has
inputs (one run for the hard-coded census/gdev programs).  Only functions in the program file are
counted; `<module>` and stdlib frames are excluded.  The listed functions are the first ones that
reach 80% of that program's own time.

| program | hot function | own time | typed path | first refusal when not typed |
| --- | --- | ---: | --- | --- |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t237.py` | `main` | 90.6% | no (whole program) | `numeric list field assignment requires float` (line 12) |
| `lab/census/programs/gdev/g00_010.py` | `title_case` | 78.2% | yes (whole program typed) | -- |
| `lab/census/programs/gdev/g00_010.py` | `main` | 5.3% | yes (whole program typed) | -- |
| `lab/census/programs/dev/t024.py` | `main` | 73.0% | yes (whole program typed) | -- |
| `lab/census/programs/dev/t024.py` | `is_prime` | 13.9% | yes (hybrid clone) | was `division or power can raise`; fixed |
| `lab/census/programs/gdev/g18_008.py` | `run_length_encode` | 53.7% | yes (whole program typed) | -- |
| `lab/census/programs/gdev/g18_008.py` | `main` | 16.0% | yes (whole program typed) | -- |
| `lab/census/programs/gdev/g18_008.py` | `<genexpr>` line 9 | 15.1% | yes (whole program typed) | -- |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t131.py` | `main` | 90.5% | yes (whole program typed) | -- |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t380.py` | `main` | 69.3% | yes (whole program typed) | -- |
| `lab/corpus/programs/deepseek-v4.1-flash-free/t380.py` | `<lambda>` line 18 | 11.8% | yes (whole program typed) | -- |
| `lab/census/programs/dev/t434.py` | `read_employees` | 61.5% | no | class `Employee` refusal, below |
| `lab/census/programs/dev/t434.py` | `_optional` | 11.6% | no | scalar `str | None` is not built |
| `lab/census/programs/dev/t434.py` | `__post_init__` | 9.0% | no | class `Employee` refusal, below |
| `lab/census/programs/gdev/g15_020.py` | `main` | 52.1% | no | `'sys' is read before it is assigned` (line 11) |
| `lab/census/programs/gdev/g15_020.py` | `unbounded` | 46.2% | yes (typed as a function) | main still refuses; the recursive call keeps it out of the hybrid |

## What was fixed

The mixed-mode/hybrid body gate refused every division, modulo and subscript.  It now allows
division and modulo (the existing `pymix` rule already refuses a candidate whose trap could reach a
boxed `try`), and a slice only when its step is a constant non-zero integer.  A run-time step and a
literal zero step stay in CPython because they can raise `ValueError`/`TypeError`; this also keeps
the old blanket slice allowance from hiding `xs[::0]`.

The hybrid analysis now seeds an annotated result kind as well as the parameter kinds, and fills
the missing `str`-slice kind in `pymix`'s inference.  That reach is needed for `str`-returning typed
helpers (`def head(s: str) -> str: return s[:2]`); `analyze` still refuses a function whose return
branches disagree with the annotation.

`is_prime` is the one hot function of these eight that the change moves onto the typed hybrid path:
`t024` now reports `accelerated: ["is_prime"]`, and all three public inputs match CPython.

## Follow-ups (big features, not implemented here)

1. **Void/`main` hybrid ABI** -- blocks 6 of the 16 hot entries (`main` in `t237`, `t024`, `g18`,
   `t131`, `t380`, `g15`).  Mixed mode refuses them with
   `unresolved-return | no return, or contradictory returns`; the extension ABI only carries
   scalar/list results.  A `main` clone also reads stdin and prints, so it needs a safe
   stdin/stdout bridge, not just a `void` return.
2. **`t237` heterogeneous `list[float]`** -- CPython keeps the ints stored into an annotated
   `list[list[float]]`; AIL's typed list is a `double` array, so accepting the store would print
   `22.0` where CPython prints `22`.  First message:
   `numeric list field assignment requires float`.
3. **`t434` dataclasses/`Optional`/csv** -- the generated ordered comparison returns a bool or
   `NotImplemented`; the typed bool slot cannot carry `NotImplemented`:
   `the result of __lt__() is declared bool, but `(self.name < other.name if self.name ...` is not a
   bool`.  A scalar `str | None` is also not built, and the general path refuses
   `a **kwargs call argument`.  A `read_employees` clone would return `list[Employee]`, outside the
   mixed-mode ABI.
4. **`g15` recursion limit** -- `sys.getrecursionlimit()` is not built
   (`sys.getrecursionlimit (not yet published in NAMES_library.json)`), and `sys.setrecursionlimit`
   is currently lowered to a no-op.  The typed recursion guard dies at the compile-time
   `AIL_MAX_RECURSION_DEPTH` with `ail_die`, not with a catchable `RecursionError` at a runtime
   limit, so `unbounded` cannot be accelerated without changing that mechanism.
