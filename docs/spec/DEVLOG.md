# Development log

## 2026-10-22 -- job-integ1-10230230: integrate four accepted jobs

Integrated the fix commits of `job-c169-10221631`, `job-cov6-10221632`, `job-fuzz8-10221632` and
`job-intenum4-10221632`, skipping their `.agent/` and `corpus/` changes. The c169 records live in
`docs/spec/`; the other three write the root records. Conflicts were limited to `MANIFEST.json`
(union of pins) and the shared `DEVLOG.md` / `DIFFERENCES.md` (both sides kept). Placeholder
difference ids were numbered C170-C187. Targeted tests and the full suite were run on the final
commit.

## 2026-10-22 -- C169 review fix: self-referential receivers no longer recurse

Passing the same `seen` set through `value_class`/`attribute_class` into `name_class` makes a
receiver that is re-bound through its own attribute (`b = b.other`, or a chain of such bindings)
resolve to unknown instead of restarting the walk with a fresh set and overflowing the stack.
The general path then answers CPython's result; the typed-only build refuses the self-referential
class by name.  `test_ail_c169.py` adds the cycle case for both general/default builds and asserts
the typed path's named refusal.

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
