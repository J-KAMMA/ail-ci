# fcfloat1: written list[float] parameters and nested-list parameters from call sites

Base: `origin/job-callinf1-op1106` bb35fcb68 plus fclist1's three commits cherry-picked
(cc4a29473, 1eb2f7156, 329235bf6; one conflict in `manifest.d/45.txt`, regenerated).

## Before (pyproof, full census, `-j 2`)

| tree | typed | general | refused | wrong |
|---|---:|---:|---:|---:|
| callinf1 alone (its own record) | 31 | | | 0 |
| callinf1 + fclist1 (this branch's base) | 34 | 13 | 8 | 0 |
| this branch | 35 | 12 | 8 | 0 |

With both stacks, `scimark_fft` and `spectral_norm` are already typed: callinf1 gives `xr`/`out`
the list[float] kind from their call sites, and fclist1's `_scan_written_lists` (kind-agnostic)
plus its `list[float] parameters are read-only` exemption let the stores through. A list[float]
parameter is an `ail_flist` passed by value whose `p` is the caller's buffer, so an element store
(`ail_flist` set, bounds-checked, never resizing) is seen by the caller; `_written_list_argument`
accepts only a local list[float], the function's own written parameter or a fresh display.

## nbody

`bodies` is an unannotated parameter. `nested_lists.rewrite` lowered `main`'s
`bodies = [[0.0, ...], ...]` to rows (`list[_AilRow_float]`), and callinf1 then gave `advance`'s
parameter that kind, but the lowering had not rewritten `advance`'s body (`bi = bodies[i]; bi[0]`),
so the typed path met `bi[0]` on a row object: `subscripting a list[float]` (the row kind
`('obj', '_AilRow_float')` spelled by `nested_lists.explain`).

Fix: `NestedLists.infer_params` (nested_lists.py). An unannotated parameter of a plain top-level
function that every call site hands the same `list[list[T]]` local is treated as annotated
`list[list[T]]` before the lowering runs, so `bi[0]` becomes `bi.v[0]` and `bi = bodies[i]` shares
the caller's row exactly as CPython does. Conditions: not the entry, not a library build, not a
legacy grid function, never used as a value, no defaults/varargs/keywords/decorators, every call
plain positional with exact arity, each argument a bare name, the call directly in a function body
(no lambda, comprehension or nested def around it; a module-level call disqualifies), the
parameter never rebound in the callee, and every site agreeing on T.

## After

| program | before | after | output |
|---|---|---|---|
| lab/pyperf/bench/nbody.py | general | typed | matches |
| lab/pyperf/bench/scimark_fft.py | typed (base stack) | typed | matches |
| lab/pyperf/bench/spectral_norm.py | typed (base stack) | typed | matches |

Default sizes (nbody 400000, fft 2048, spectral 700), typed vs `AIL_UNIFIED_FORCE=1` general build:

| program | icount typed | icount general | RSS typed | RSS general | RSS CPython | wall typed | CPython |
|---|---:|---:|---:|---:|---:|---:|---:|
| nbody | 435.7M | 19,089.5M | 1.6 MB | 10.3 MB | 10.5 MB | 0.03 s | 2.0-4.0 s |
| scimark_fft | 294.5M | 13,164.4M | 2.3 MB | 10.4 MB | 10.8 MB | 0.016 s | 1.5-1.7 s |
| spectral_norm | 490.3M | 17,092.8M | 1.6 MB | 10.0 MB | 10.5 MB | 0.028 s | 2.9-3.2 s |

Binary: 31.5 / 30.7 / 26.4 KB typed vs 158 / 141 / 129 KB general.

## Probes (`lab/reach/fcfloat1/`, default build and `AIL_UNIFIED_FORCE=1`, vs python3)

All 17 match CPython (stdout and exit status) in both builds. Floats are printed with repr.
Typed in the default build: p01 same list twice, p03 NaN/inf, p04 -0.0, p06 empty list, p07
negative indexes and IndexError (exit 1), p10 nested list passed twice, p12 int grid, p13 appends
through a nested parameter, p14 rebound parameter, p15 module-level call. General, as CPython
needs: p02 `b = a` alias, p05 int stored into a float list (CPython keeps the int `0`), p08 printing
a nested list, p09 two element kinds at the call sites, p11 shared row, p16 int stored into a float
row, p17 operand order. p10, p12, p13 and p15 move from general to typed with this branch.

## Generated C

Base (this branch's base, 329235bf6) vs branch, `--debug-dir`:
- lab/compare/src/*/{main,typed}.py: 16 `program.c` byte-identical, 3 general-path builds identical
  debug dirs, chain_relax/main.py refused in both (int64 overflow);
- the typed rows of `lab/pyproof/results.jsonl`: 17 `program.c` byte-identical; 6 FFI examples
  identical except the `ail_object_*`/`ffi_*` hashes of the compiler package files; 6
  examples/crate programs need their `ail_cargo.py` stubs and were not built.
So icount of every previously typed program is unchanged.
