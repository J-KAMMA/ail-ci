# DEVLOG

## 2026-10-24 -- pre122: non-BMP / surrogate format fill refused by name

The 16-bit general path cannot hold a non-BMP character or a lone surrogate, so
`format("x", chr(0x1F600) + ">5")` (and its f-string form) stopped with the uncatchable
`chr() non-BMP code point requires 32-bit strings` before `ail2f_parse` was reached. The general
emitter now refuses a constant `chr()` of U+10000..U+10FFFF or U+D800..U+DFFF by name at compile
time instead of leaving it to `ail_bi_chr`'s internal stop. BMP fills (Latin-1 and non-Latin-1),
BMP `chr()`, and out-of-range `chr()` (still CPython's `ValueError`) are unchanged. Added
`test_ail_pre122.py` and `DIFFERENCES.md` row `C?-job-pre122-10242315-1`.

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
