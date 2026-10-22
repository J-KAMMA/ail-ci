# Development log

## 2026-10-22 -- C169 review fixes: receiver class and rebinding in typed bounds

The typed list lowering now resolves an `obj.field` index bound against the receiver's visible
class -- a parameter/local annotation, constructor assignment, alias or `self` field chain -- and
falls back when it cannot.  It no longer accepts any class's same-named field, which made a float
field look like an int when another class declared that name as int.  `index_name_kind` now treats
tuple, starred, with, except, import, walrus, comprehension and nested-definition bindings as
unknown instead of reusing an earlier int assignment.  `test_ail_c169.py` builds the typed-lowering
case with `AIL_NO_GENERAL=1` (so it no longer silently exercises the general fallback) and adds
regression cases for class-field receivers and tuple/starred bindings.

## 2026-10-22 -- C169 review fixes: typed list.index bounds and long __index__ names

The default typed list lowering now classifies `list.index` start/stop bounds: visibly int/bool
bounds keep the fast loop, visibly non-index ones (None, float, str, ...) raise the slice-index
TypeError, and anything else (including objects with `__index__`) goes to the general path, which
performs CPython's full conversion.  A local typed list therefore no longer coerces a float bound.
`__index__ returned non-int (type ...)` now formats the complete type name: the general runtime grows
its name buffer to the class name's length and the bound check sizes the message accordingly.
`test_ail_c169.py` gained local typed-list, int64-width and long-name cases.

## 2026-10-22 -- C169: list.index / tuple.index bounds

Closed C169.  The general path now evaluates a start/stop bound once, converts an instance through
`__index__`, and raises CPython 3.12's slice-index TypeError for `None`, floats, strs and other
non-index values (including `__index__` returning a non-int).  The same check covers list, tuple and
deque; str's own None-as-default behaviour is unchanged.  New tests: `AIL_CURRENT/test_ail_c169.py`.
