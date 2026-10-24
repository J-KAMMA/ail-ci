# DEVLOG

## 2026-10-24 - qtest1: str search start/end bounds use __index__

`str.startswith`/`endswith` (and `find`/`count`/`index`) read an instance start/end
as its pointer payload after the general path's tag check rejected `AIL_T_INST`.
`"abcabc".startswith(("bc",), Idx(1))` with an `__index__` class printed a caught
TypeError where CPython returns True. The shared str window now converts an
instance bound through `__index__` with CPython's slice-index messages (None still
means the default bound), and the static check admits instances so the runtime
conversion is reachable. Added `AIL_CURRENT/test_ail_qtest1.py`; tuple prefixes,
empty prefixes, None, negative/huge bounds and wrong types stay compared on both
builds.

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
