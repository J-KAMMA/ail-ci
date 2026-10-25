# Development log

## 2026-10-25 - pre189 review fix: instance shadowing, __dict__, class values

Review follow-up. A computed `getattr(obj, name)(...)` now checks the instance attribute table
before the method table, so an instance field named like a method (own or inherited) is the value
CPython calls; a non-callable field raises CPython's TypeError. `getattr(obj, "__dict__")` is no
longer offered as a detached copy: a literal name is refused at compile time and a computed name
by name at run time, while `hasattr` still answers True as CPython does. `getattr` / `hasattr` on
a class value reached through a variable, an argument, a list item, an attribute or a dict value
now read the class attributes (MRO first) and `__name__`; a method or property value, `__dict__`,
`__class__`, a non-program class and every `setattr` on a class value are refused by name.
Recorded as C?-job-pre189-10251546-1/-2. Probes `/tmp/probes/p1`-`p7` cover own/inherited and
static/class method shadowing, the computed and literal `__dict__` refusals, class attributes
through all four routes, inherited/zero/negative/empty/None values, shared mutable class
attributes, missing names with and without a default, non-string names, class `hasattr`, class
`setattr` refusal and both builds.

## 2026-10-25 - pre189: computed method calls, instance dunders, class-attribute builtins

`getattr(obj, name)(...)` with a computed `name` now reaches a user method on both builds, not
only the literal spelling: the general path evaluates `obj`, `name` and an optional default once,
tests every user method name against the run-time string (most derived class first), and calls
the matching method with the call's arguments evaluated only in the chosen branch. An override,
a @staticmethod, a @classmethod, a default argument and the value arriving through an argument, a
list item, an attribute or a dict value all match CPython; a positional-argument mismatch raises
CPython's TypeError text instead of falling through to AttributeError. A name that is not a method
still takes the ordinary attribute route, including `getattr(obj, name, default)(...)`.

An instance now answers `hasattr(obj, "__class__")` and `hasattr(obj, "__dict__")` with True, and
`getattr(obj, "__dict__")` returns the same mapping as `vars(obj)` (dunders and an exception's
`args` slot excluded); `getattr(obj, "__class__")` is the run-time class object.

`getattr` / `hasattr` / `setattr` on a class value (including `vars`) are refused by name at
compile time on both builds. A class here keeps its methods and class attributes outside the
instance attribute table, so there is no run-time mapping to read or write; CPython accepts these
calls, so the refusal is recorded in DIFFERENCES (C?-job-pre189-10251546-1).

Added `AIL_CURRENT/test_ail_pre189.py` (computed method routes, instance dunders, and the class
refusal on the default and general builds). Probes `/tmp/probes/p1`-`p5` covered literal and
computed names, overrides, static/class methods, defaults, aliases, empty/non-string names,
argument / list-item / attribute / dict routes, instance and exception `__dict__`, and both
class refusal forms; all match CPython or are refused by name.

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
