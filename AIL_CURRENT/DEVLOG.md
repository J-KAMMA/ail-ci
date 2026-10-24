# DEVLOG

## 2026-10-24 - comprehension stores and binary64 copies (job-perf6-10240916)

`numeric_scale_binary` spends most of its time in the generated `float_values_scale`, whose
comprehension reserved the exact result size and then called `ail_flist_push` for every element.
For a counted, unfiltered comprehension over an int or float list, the compiler now writes
`list.p[list.n++] = value` directly when the element expression contains no calls (which is what
could move the source list under the loop). A float element built only from names, reads and
`+ - *` also gets `#pragma omp simd`; `pyc.py` adds `-fopenmp-simd` so GCC vectorizes that one
loop, while `-fno-tree-slp-vectorize` stays in force for the struct-of-doubles reason it was added.
`F64CODEC` now takes `unpack_float64`/`pack_float64` buffers from `ail_alloc_raw` instead of the
zeroing `ail_alloc`, since both paths overwrite every byte before anyone reads it.

`python3 bench/compare.py --app numeric_scale_binary`: ail/c went from 1.371 [1.360, 1.382] to
1.226 [1.217, 1.235], ail/base 0.895 [0.885, 0.906] (about 10.5% faster); output was identical and
the ranges do not overlap. Probes over int/float comprehensions (empty, negative, aliased, sliced,
argument/attribute/dict/list-item sources, calls, filters, mid-loop exceptions, repeated loops)
matched CPython on both builds.

## 2026-10-23 -- fuzz37: ordering TypeError names the written operator

Fuzzing while loops and counters against CPython on both builds found that an
ordering comparison between built-in values that cannot be ordered raised
`TypeError '<' not supported ...` for every operator.  `while s > 0` with
`s = "5"` printed `'<'` where CPython prints `'>'`, and `<=`, `>`, `>=` and
chained comparisons had the same wrong symbol.  The general-path comparison
helper now receives the operator symbol from `ail_op_lt/le/gt/ge`, passes it
through nested list/tuple comparisons, and uses it in the message; callers such
as sorting keep `<`.  Both builds now match CPython.  `test_ail_fuzz37.py`
keeps the probe.  Also seen but not changed: the general build refuses an
integer literal outside int64 range that the default build accepts, and
`sorted([1, "x"])` names the operand types in the opposite order from CPython
(`'int' and 'str'` instead of `'str' and 'int'`); both are pre-existing.
