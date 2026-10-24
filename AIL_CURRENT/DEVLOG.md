# DEVLOG

## 2026-10-24 - pre86 follow-up: validate r after materialising the pool

The reviewer found that the new eager r tag check ran before the iterable was materialised, so
`permutations(5, "x")` raised `Expected int as r` where CPython (and the base) raise
`'int' object is not iterable`. The tag test now lives in `ail_it_permutations` after
`ail__materialize`, with the boxed r rooted in the helper frame; the caller also forces the
iterable expression into a temp before evaluating r so both arguments keep CPython's left-to-right
order. `test_ail_pre86.py` gained an order/error-precedence program covering `it()/rv()`, a
non-iterable pool with a bad r, and a bad r on its own. All reviewer probes r1-r14 and the new
`/tmp/probes/p86_perm_*` probes match CPython on both builds except the pre-existing negative-r
`[]` difference and the pre-existing default-build positive-literal compile failure.

## 2026-10-24 - pre86: `permutations(xs, None)` means r=len(pool)

`itertools.permutations(iterable, None)` produced only `()` on both builds; CPython treats an
explicit None like the omitted default r and yields the full permutations. The general path lowered
r with `(r).i`, reading None as 0. The emitted call now passes the boxed r and the runtime helper
tests its tag: None means r=len(pool) (so a value arriving through a variable, argument, list item,
attribute or dict value works), an int or bool is the requested r, and any other type raises
CPython 3.12's `TypeError: Expected int as r`. The typed path already handled a literal None.
Added `AIL_CURRENT/test_ail_pre86.py` (five programs, both builds). Still observed, not changed:
negative r returns `[]` on the general path instead of `ValueError` (the open fuzz8 row) and the
default build cannot compile a positive literal r with `list(permutations(...))` (difference #2).

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
