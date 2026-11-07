# fclist1: element-written list parameters pass the caller's buffer in place

Base: `origin/integ` 8c2c99c18 (rbpyreachs8 does not touch `pyfunc.py`; its diff is optlib/noneslots
`Optional` work, so this branch does not stack on it).

## Before (pyproof `--only`, base 8c2c99c18)

| program | result | blocker |
|---|---|---|
| lab/pyperf/bench/nqueens.py | general | 'anti' is a list parameter, which is read-only |
| lab/pyperf/bench/scimark_fft.py | general | 'xi' is a list parameter, which is read-only |
| lab/pyperf/bench/spectral_norm.py | general | 'out' is a list parameter, which is read-only |

## What was built

`pyfunc._scan_written_lists` (whole program, before codegen) proves, per function, which flat list
parameters are written element by element and may be passed in place:

- callee: the parameter is only indexed (`xs[i]` read, `xs[i] = v` single-target store), measured
  (`len`), iterated (`for x in xs`) or handed to another user function; never rebound, deleted,
  resized (no method call at all), stored, returned or captured; no nested def/lambda/global/yield;
- forwarding: a parameter handed to another function's written parameter is itself written (fixed
  point); if it is not eligible the callee is dropped;
- call sites: positional, arity exact; each written argument is a local list of the calling
  function, its own written parameter, or a fresh `[c, ...]` / `[c] * k` display; the other
  arguments contain no call but `len`; the calling statement is an expression, assignment,
  augmented assignment, return, `if`/`while` test or `for` header, and outside the call it holds
  no subscript, no other mention of the passed names and no other written-list call (C operand
  order is unspecified, so nothing there may observe the store order);
- functions used as values, entries (mixed-mode clones), methods and library builds are excluded.

Codegen: a written `'array'` parameter is declared `int64_t *` (no `const`) and `xs[i] = v` is
`ail_list_set(&(ail_list){p, n, n}, i, v)` (bounds-checked, negative index as CPython, never
resizes). The caller re-checks each argument (`_written_list_argument`); a fresh `[c] * k` in an
expression/assignment/return statement is bound to a new local first
(`_hoist_written_list_displays`). Anything else keeps the old refusal.

## After

| program | result | note |
|---|---|---|
| lab/pyperf/bench/nqueens.py | typed, matches | `solve(..., int64_t *v_cols, ...)` |
| lab/pyperf/bench/scimark_fft.py | general (unchanged) | float list parameter: see below |
| lab/pyperf/bench/spectral_norm.py | general (unchanged) | float list parameter: see below |

Typed +1 of the +3 target. The two float programs are blocked by something this task's files do
not cover: an unannotated list parameter never becomes `list[float]` (FLIST) from its call sites.
`_claim` only claims INT/FLT/BYTES/BYTEARRAY/STR/'array', and `_propagate_signatures_pass`
re-derives a callee's kinds with `_param_kinds`, which drops the "handed to a sequence slot"
promotion (`eval_ata`'s `v/out/tmp` go back to `int`). So `fft(xr, ...)` and `eval_atv(v, out, n)`
compile `xr`/`out` as int64 arrays, and a float store into them is still refused (correctly).
Next step: an FLIST claim for a flat float-list local (and keeping the forwarded `'array'` kind
through re-derivation) in the signature fixed point; that changes kinds program-wide, so it
needs its own byte-identity run.

## Probes (`lab/reach/fclist1/`, default build and `AIL_UNIFIED_FORCE=1`, vs python3)

See the report in the job notes; every probe matches CPython in both builds, except p08/p20, whose
CPython output needs an int beyond int64: both builds print the int64 lines and stop with exit 1
and an overflow message (the int64 default, decided 2026-10-31); the forced general build does the
same, so this is not new.

Default build typed: p02 (same list twice), p11 (empty list), p14 (mutation visible to the
caller), p15 (negative indexes, IndexError), p16 (module-level call), p08/p20 (int64). Default
build general, as before: p01 repro (`return xs`), p03 grid row, p04 dict value, p05 `f(xs) is
xs`, p06 global store, p07 append while iterating, p09 `b = a`, p10 list of lists, p12 float
list, p13 operand order (`a[0] + bump(a)`), p17 forwarding through an int-defaulted parameter,
p18 `print` of a bool list, p19 `print(perm(a), a)`.

## Generated C

- `lab/compare/src/*/{main,typed}.py`: 16 builds byte-identical `program.c` base vs branch; the
  other 4 are general-path builds (no `program.c`). Identical C, so icount is unchanged.
- the 30 programs typed in `lab/pyproof/results.jsonl`: 18 byte-identical `program.c`, 3 debug
  dirs identical, 6 FFI examples differ only in the `ail_object_abi_<hash>` symbol (a hash of the
  compiler package files), and 3 are the three targets above.
- `AIL_CURRENT/test_ail_fclist1.py`: 2 tests OK (all probes and the three programs, both builds).
