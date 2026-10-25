# DEVLOG

## 2026-10-25 -- statically known unary int64 overflow (job-rbpre172-10251601)

The first pre-existing difference left by job-pre108 was pure unary overflow: `-MIN`, both on a
module constant and as `-(-9223372036854775808)`, compiled on the default build and then stopped at
run time with `integer overflow`, while CPython printed a bignum; the general path refused the
`MIN` literal with a different message. A new front-end check evaluates unary `+`/`-` over integer
literals and module-level int constants and refuses an out-of-int64 result by name (`int64 constant
expression out of range: ...`) on both builds. A module constant shadowed by a parameter is not
folded, and values that only reach the unary operation as variables keep the fixed-width trap.
Added `test_ail_pre172.py` and registered it in `ail_check.MODULES`.

## 2026-10-24 -- bytes.count memmem: self-contained declaration (job-perf7-10240917)

Review found the short-needle `bytes.count` path called `memmem` without a declaration in the
emitted C, so `gcc -std=c11` (a mode AIL uses for `to_c` and C-object builds) assumed an implicit
`int` return and truncated the pointer (segfault). The `BYTES` block now declares `memmem`
itself on non-Windows, after `<string.h>`; glibc and musl both export the symbol, and the
declaration is compatible with the header's when `_GNU_SOURCE`/`_DEFAULT_SOURCE` is set.
`rp7_count_small.py` now prints `4 2 2` under `-std=c11 -O2` and `-std=gnu17`; all count probes
match CPython on both builds, and `binary_search` is unchanged at 64.9 ms vs base 92.0 ms
(`ail/base 0.711 [0.706,0.717]`). Required tests pass.

## 2026-10-24 -- bytes.count: memmem for short needles (job-perf7-10240917)

`binary_search` (`count` of a 7-byte needle over a 64 MiB file) spent ~69 ms of its 94 ms in
`ail_bytes_count_range`, which used the byte-pair Horspool scan. For a short needle glibc
`memmem` is about twice as fast on the same data (38 ms vs 71 ms), so the non-Windows
short-needle path now uses the same non-overlapping `memmem` loop as the C reference; Windows
keeps Horspool. `bench/compare.py --app binary_search`: base 98.2 ms, new 69.2 ms
(AIL/C 1.414 -> 0.994, ranges non-overlapping). Probes for empty, negative, windowed and
64-byte needles through arguments, list items, attributes and dict values match CPython on both
builds.
## 2026-10-24 -- pre173: bytes start/end bounds use CPython's slice-index rules

The general path's bytes/bytearray `find`, `rfind`, `count`, `index`, `rindex`, `startswith` and
`endswith` read the optional start/end bounds straight from the boxed value, so `b"abc".find(b"a",
"x")` raised `'<' not supported between instances of 'str' and 'int'` instead of CPython's
`slice indices must be integers or None or have an __index__ method`.  One C primitive
(`ail2b_index` in safetyrt.py) now converts a bound exactly as `_PyEval_SliceIndex` does: an int, a
bool or an instance's `__index__` (with CPython's `__index__ returned non-int (type ...)` when the
result is not an int); `None` keeps its default.  `_ail_b_rng` keeps the clamping, and all seven
methods share it.  `test_ail_pre173.py` covers both builds and keeps the case.

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
