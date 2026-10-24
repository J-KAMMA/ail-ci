# DEVLOG

## 2026-10-24 - pre125: module-scope bare attribute/subscript annotations

CPython evaluates the target's base object and index expressions, then the annotation
expression, for `obj.attr: note()` / `xs[i]: note()` at module scope (and stores neither).
Both builds silently ran neither. Since this compiler cannot evaluate type syntax as a value,
the Python surface now refuses the construct by name before codegen, with the plain-assignment
rewrite. A bare annotation on a name (`count: int`) is unchanged. Added
`test_ail_pre125.py`; probes in `/tmp/probes` (`ann_attr_module.py`, `ann_sub_module.py`,
`ann_attr_simple.py`, `ann_sub_simple.py`, `ann_sub_getitem.py`, `ann_attr_undef.py`,
`ann_sub_undef.py`, `ann_attr_name_target.py`, `ann_sub_name_target.py`,
`ann_attr_alias.py`, `ann_sub_dict_str.py`, `ann_sub_routes.py`, `ann_sub_empty_negative.py`,
and `ann_name_type.py`).

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
