# DEVLOG

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
