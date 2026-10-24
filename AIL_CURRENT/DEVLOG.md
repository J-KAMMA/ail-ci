# DEVLOG

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
## 2026-10-24 - pre125: module-scope bare attribute/subscript annotations

CPython evaluates the target's base object and index expressions, then the annotation
expression, for `obj.attr: note()` / `xs[i]: note()` at module scope (and stores neither).
Both builds silently ran neither. Since this compiler cannot evaluate type syntax as a value,
the Python surface now refuses the construct by name before codegen, with the plain-assignment
rewrite. A bare annotation on a name (`count: int`) is unchanged. Added
`test_ail_pre125.py`; probes in `/tmp/probes` (`ann_attr_module.py`, `ann_sub_module.py`,
`ann_attr_simple.py`, `ann_sub_simple.py`, `ann_sub_getitem.py`, `ann_attr_undef.py`,
`ann_sub_undef.py`, `ann_attr_name_target.py`, `ann_sub_name_target.py`,
`ann_attr_alias.py`, `ann_sub_dict_str.py`, `ann_sub_routes.py`, `ann_sub_empty_negative.py`,
and `ann_name_type.py`).
## 2026-10-24 -- out-of-range int64 constant expressions are refused by name

Only a bare integer literal was checked against int64. A pure integer constant expression that left
the range (`10 ** 30` in a return, argument, list item, attribute, dict value or module constant)
was lowered and stopped at run time with `integer overflow`, and `__index__` returning `10 ** 30`
printed a misleading sequence `TypeError`. `_check_int64_literals` now evaluates pure integer
constant expressions (with guards for huge exponents and shifts) and refuses an out-of-range value
at compile time with `int64 literal out of range`, on both builds. In-range expressions such as
`2 ** 62`, `(1 << 62) - 1`, `-(2 ** 62)` and `2 ** (63 - 1)` are unchanged. `test_ail_pre159.py`
holds the literal, expression, `__index__` and value-path cases and the in-range CPython check.

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
