# DEVLOG

## 2026-10-24 - pre54: round() at the int64 boundary is refused by name

The pre35 review recorded `z_intmin` (`round(-9223372036854775808.0)` then `abs`, unary `-`, `* -1`)
as a pre-existing difference: CPython's unbounded int answers 2**63, while both builds compiled the
program and stopped later with `integer overflow`.  The rounded value is INT64_MIN, which is
representable, but its magnitude is not; the value is known at compile time, so a one-argument
`round()` of a constant float at or beyond the int64 boundary is now refused by name in
`pyc.build` on both builds rather than compiled into a program that stops later.  Values just
inside the boundary, two-argument `round()` (a float result) and a user-defined `round` are
unchanged.  Added `AIL_CURRENT/test_ail_pre54.py` and registered it in `ail_check.MODULES`.
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
