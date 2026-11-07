# Development log

## 2026-11-07 -- spec1 review fixes: examples, recursion, stale claims (job-spec1-11071506)

Fixed the eight review defects in `docs/SPEC/` and `docs/ROADMAP.md`. Added the missing examples
for VT6, VT9, VT13, AR9, AR12 and CO4; added EO10 (the fixed 50,000-frame recursion guard and the
loud `RecursionError`) to the INVENTORY and the evaluation-order chapter, and narrowed OPEN O8 to
the limit value alone. Replaced the missing `docs/STDLIB.md` citation with
`AIL_CURRENT/docs/design/STDLIB_REACH.md`, corrected the proof line to the closed property
vocabulary (`could not prove bounds`), and rewrote the ROADMAP paragraph to state the
future-standard goal in two sentences with the specification link. Corrected two false status
claims found by probes: MO2 is now **partly** (general path matches; the default build does not
compile the list-in-list example on this tree) and AR8 is now **partly** (literal and constant
complex results are refused; a run-time result still prints `nan` on the default build, the known
bug in MIGRATING item 11). No compiler or test change. Probes: `mo2.py`, `ar8_literal.py`,
`ar8_const.py`, `ar8_runtime.py`, `recursion_2000.py`, `recursion_60000.py`, `vt6_bool.py`,
`vt9_codecs.py` under `bash ~/tools/cmp.sh`; results as stated in those rules.

## 2026-11-07 -- spec1: first draft of the language specification (job-spec1-11071506)

Wrote `docs/SPEC/`: `README.md` (purpose, rule ids, status vocabulary, versioning),
`INVENTORY.md` (the numbered rules with their sources), eight chapters (values, arithmetic,
evaluation order, memory, concurrency, modules/FFI, diagnostics, compatibility) and `OPEN.md`
(the owner decisions, with options, cost and recommendation). The chapters state the rule, an
example, the CPython difference, the status and the proof; they cite `docs/spec/DIFFERENCES.md`,
the design notes and the test modules rather than inventing a second source. Also added two
sentences to the "What AIL is for" section of `docs/ROADMAP.md` saying that the semantics are
AIL's own and CPython output is a compatibility mode. Docs only: no compiler change. The general
rule the draft fixes is "a program has the specified meaning or is refused by name; it never
silently has a different meaning".

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
