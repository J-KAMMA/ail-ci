# DEVLOG

## 2026-10-24 - pre104: round() of nan/inf raises CPython's exception

The pre54 review recorded the default build's one-argument `round()` of nan/inf as a
pre-existing difference: it stopped through `ail_die` with `round() of nan` or
`round() result does not fit in this language's int64`, so a `try` could not catch it and an
uncaught program printed the trap message instead of CPython's exception line.  `ail_round0`
now raises `ValueError("cannot convert float NaN to integer")` and
`OverflowError("cannot convert float infinity to integer")` through the normal exception path
on both builds.  Finite values, including the int64-boundary trap, are unchanged.  Added
`AIL_CURRENT/test_ail_pre104.py` and registered it in `ail_check.MODULES`.
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
