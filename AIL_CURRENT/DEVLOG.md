# DEVLOG

## 2026-10-24 -- pre26: repr(e.args[i]) keeps the argument's kind

On the typed path `e.args[i]` reads as text, so `repr(e.args[i])` repr'd that text: a
`ValueError(3.0)` handler printed `'3.0'` where CPython prints `3.0`, and int, bool and None
arguments were quoted the same way.  The handler rewrite now lowers `repr(e.args[i])`,
`f"{e.args[i]!r}"` and `%r` of one argument to a new `_ail_exc_arg_repr` accessor that formats
the stored argument (a str keeps its quotes, a number does not).  Both builds agree with
CPython; `test_ail_pre26.py` keeps the probe, including negative and out-of-range indexes.

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
