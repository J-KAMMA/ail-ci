# DEVLOG

## 2026-10-24 -- pre152: `C.__name__` on a class read as a value

`C.__name__` raised `AttributeError: 'type' object has no attribute '__name__'` on both
builds: the general path hands a class to `ail_inst_getattr` as an `AIL_T_CLASS` value, and
that helper accepted only INST/EXC receivers. It now answers CPython's `type.__name__` (the
class's own name, so a `__name__` in the class body or a base no longer shadows it, matching
CPython's data descriptor), and the missing-attribute message for a class receiver is
CPython's `type object 'C' has no attribute 'x'`. The same path covers a class kept in a
variable, passed as an argument, or reached through a list item, a dict value or an
attribute. Probes in `/tmp/probes/q1.py`-`q10.py` (both builds) match CPython; builtin type
names as plain values (`int.__name__`) remain refused by name. New test:
`test_ail_pre152`.

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
