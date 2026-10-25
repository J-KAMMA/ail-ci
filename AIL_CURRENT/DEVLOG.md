# DEVLOG

## 2026-10-25 -- int64 constant refusal review fix (job-pre108-10251451)

The 4096-bit evaluation cap silently returned "not a constant", so `2**5000`,
`(2**5000) >> 4999` and `(10**5000) // (10**4999)` compiled and trapped at run time. A
constant over the cap is now marked too big and refused by the same
`int64 constant expression out of range` name. The maxsplit exception is narrowed to the
constant maxsplit of a literal `str.split`/`rsplit`, where it emits the pre97 maxsplit refusal
name; a user method named `split` and a non-constant maxsplit (list item, conditional, call)
stay under the generic check, so their huge constants are refused instead of trapping. Both
builds and the integration copies of `test_ail_pre97`, `test_ail_pre113` and
`test_ail_typed_tuples` pass.

## 2026-10-25 -- int64 constant refusal judges the whole expression (job-pre108-10251451)

The pre108 front-end check refused any constant subexpression that left int64, so it broke the
whole-expression folds added by pre113 (`2**65 - 2**65`, `(1 << 63) - 1`) and the maxsplit
refusal that pre97 owns (`str.split(..., 10**30)` printed the generic message instead). The check
now evaluates the outermost all-int expression exactly with Python's unbounded integers (bounded
to 4096 bits) and refuses only when the result is outside int64; `str.split`/`rsplit` maxsplit
arguments are left to the lowering that names the CPython OverflowError. `test_ail_pre108` and
the rebuilt integration copies of `test_ail_pre97`, `test_ail_pre113` and
`test_ail_typed_tuples` pass.

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
