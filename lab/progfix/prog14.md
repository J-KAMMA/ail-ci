# prog14 -- typed reach of eight real programs

Profiler: CPython 3.12 `cProfile`, with the module-level imports executed before the profile and
`main()` profiled, so startup/import time is not counted as program work.  The four stdin-driven
programs were given a scaled input (`/tmp/profdata/*.in`: t341 n=2,000,000; t168/t164 60,000 CSV
rows; t318 100,000 integers) so a hot function is visible; the gdev programs do their fixed work.
"own" is cProfile `tottime`.  The hot set is the functions that together hold >= 80% of the user
function time.

| program | hot function(s) (own time) | share of user time | typed before | typed after / first reason |
| --- | --- | --- | --- | --- |
| g02_002 | `proper_divisor_sum` 0.031 s | 97% | mixed-mode candidate, but the hybrid refused it: `division or power can raise` | **accelerated**: divisor `i` is a local every binding keeps positive (`i = 2; i += 1`) |
| t341 | `count_valid` 0.112 s | ~100% | not selected: `unresolved-return` (tuple assignment `a, b = b, (a + b) % MOD`); the slice also dropped `MOD` | **selected + accelerated**: tuple inference and literal module constants; `% MOD` and `range` pass the gate |
| g15_038 | `main`, `symbolic_name`, `make_error`, `round_trips` (all below cProfile's 1 ms) | n/a (<1 ms total) | no: `main`/`make_error`/`symbolic_name` `unresolved-return`; `round_trips` `to_c-refused` (`getattr`) | still no. Follow-up: OSError/tuple/dict module helpers and `getattr`; `symbolic_name` also hits `a method on Attribute` for `errno.errorcode.get` |
| g16_036 | `inorder` (64/16 recursive calls) | n/a (<1 ms total) | no: `unresolved-param tree`; `Tree = Optional[Tuple[...]]` is not a supported annotation | still no. Follow-up: generators (`yield`/`yield from`) and `Optional[Tuple[...]]` values |
| t168 | `main` 0.031 s own (plus csv internals) | 18% own; `main` is the only user function in the hot path | default build compiles the whole program typed; the hybrid has no unit for `main` (`unresolved-return`, None result, csv/print calls) | still runs `main` in CPython. Follow-up: hybrid functions returning None that call/I/O |
| g25_012 | `main`, `categorize` (12 calls, <1 ms) | n/a (<1 ms total) | no: `categorize` `to_c-refused` -- `a `match` statement.` | still no. Follow-up: lower `match` (literal/class/wildcard cases and guards) to an if/elif chain in the typed emitter |
| t318 | `update` 0.069 s, `main` 0.069 s, `query` 0.060 s | 87% | no: `update`/`query` are nested functions (pymix selects top-level functions only); whole program falls back on `'tokens' is a blist` | still no. Follow-up: typed clones for nested functions that capture a list, or a typed whole-program path for this shape |
| t164 | `main` 0.068 s own (plus csv internals) | 31% own; `main` is the only user function in the hot path | no: `unresolved-return`; typed whole program falls back on `a method on BoolOp` and `csv` | still no. Follow-up: csv parsing / container-returning main on the typed path |

## Fixes in this job

1. `pymix` infers tuple assignments element by element (RHS first, so simultaneous assignment is
   not read as sequential), and `pymix`/`pyboxed2` keep top-level literal constants in the
   candidacy/emission slice.  This turns t341's `count_valid` from `unresolved-return` into a
   selected function.  It is also required because the slice previously made `to_c` say
   `'MOD' is read before it is assigned`.  Only a constant the emitter accepts (int/float/str/
   bytes scalar, numeric list/tuple, or list/tuple of str) and bound exactly once is kept: a
   set/dict literal, a second assignment, `+=`, a `for` target and a `global` write are not one-time
   constants, so the clone is refused instead of compiling the first literal as final.
2. The hybrid body gate now allows `%`, `//` and `/` only when the divisor is a positive literal,
   a local whose every binding keeps it positive, or a nonzero literal module constant; `Pow`
   stays out.  This makes g02_002's `proper_divisor_sum` safe to wrap and unblocks `count_valid`'s
   `% MOD`.
3. The gate allows `range(...)` and `len(...)` while those names are the builtins (not shadowed at
   module scope, by a parameter/local, or by a nested def).  Passing a list parameter to `len`,
   `sum`, `min`, `max`, `sorted`, `any` or `all` is not treated as passing it to a mutator.  The
   other call, subscript, attribute-store, raise/try and generator refusals are unchanged.
4. A module constant is proven only when it is the name's sole binding at module scope and no
   function writes it under `global`.  `MOD = 7; MOD += -4`, `for MOD in ...` and a `global MOD`
   writer therefore stay in CPython (the slice drops the stale literal), and the ten `lab/compare`
   generated C files are unchanged.
5. A local is proven positive only by a positive literal assigned unconditionally at the function's
   own top level before every read, with every other binding a positive literal or `+=` of one.
   A parameter (even one later reassigned), a tuple/`for`/`with` target, a branch-only binding, a
   boolean, and a read before the binding are not proven.  This closes the parameter-rebind and
   loop-variable holes the first version of the proof had.

Bad divisors stay in CPython: a parameter divisor, a divisor reached through a list item, attribute
or dict value, a literal zero or negative local, a boolean, or any name whose bindings are not all
positive are not proven.  No int is wrapped; the existing overflow flag and CPython fallback still
apply.

## Follow-ups (bigger features, exact first messages)

- `match` in g25_012/`categorize`: `a `match` statement.` (write an if/elif chain).
- generators and tuple-shaped annotations in g16_036/`inorder`: `'tree' is annotated Tree, which
  this compiler has no rule for.` and `yield: this language has no generators.`
- nested functions in t318/`update`,`query`: `'tokens' is a blist; ...` and no per-nested-function
  selection.
- module/exception values and `getattr` in g15_038: `call to getattr(); ...` and
  `a method on Attribute` (`errno.errorcode.get`).
- hybrid functions returning None / doing I/O (t168, t164 `main`, g15 `main`): `result kind None
  stays in CPython` / `a call can raise or have side effects`.
