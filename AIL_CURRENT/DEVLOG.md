# DEVLOG

## 2026-10-24 -- statically known int64 constant overflow (job-pre108-10242222)

The pre-existing `ttypes.py` difference used `[9223372036854775807 * 2, ...]`: CPython prints
bignums, while AIL compiled the program and then stopped at run time with `integer overflow`. A new
front-end check evaluates integer constant expressions built from literals and module-level int
constants (`+`, `-`, `*`, and `**` with a non-negative exponent) and refuses an out-of-int64
result by name (`int64 constant expression out of range: ...`) on both the general and the default
build. The check is conservative: a module constant shadowed by a local or a parameter is not
folded, shifts keep their existing refusal messages, and values that only reach the operation at
run time still trap with `integer overflow`. Added `test_ail_pre108.py` and registered it in
`ail_check.MODULES`.

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
