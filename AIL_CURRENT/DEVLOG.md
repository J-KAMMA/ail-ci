# DEVLOG

## 2026-10-24 -- pre41: nested generator expression as an any()/all() iterable

A reviewer of pre28 recorded that an inner generator expression used as the iterable
(`any(x for x in (y for y in ...))`) is materialised eagerly. The general path still
builds the inner `GeneratorExp` as a list before the outer scan, so elements after the
deciding one run their side effects: with `mark()` printing each value,
`any(x for x in (mark(i) for i in [0, 1, 2]))` printed `inner 0`, `inner 1`, `inner 2`
where CPython stops after `inner 1`. The current emitter cannot model a lazy nested
generator, so the general path now refuses that shape by name at compile time on both
builds instead of answering differently. Generator expressions over eager iterables
(lists, ranges, arguments, list comprehensions) still build unchanged. Added
`test_ail_pre41.py` (8 refused shapes, one eager program compared with CPython).

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
