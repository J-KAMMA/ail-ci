# Class-hierarchy reach on the typed path

Measurement for job `cls1` (2026-11-01). Thirty small Python programs exercise single and
multi-level inheritance, `super().__init__`, `super().method()`, an override called through a
base-typed list, `isinstance` / `issubclass`, class attributes shadowed in a subclass, and
abstract-style methods that raise `NotImplementedError`.

Each program was run three ways:

* CPython 3.12 is the oracle.
* `AIL_NO_GENERAL=1` asks for the typed path alone; it succeeds only when the program is typed.
* the default build uses the typed path when it can and otherwise falls back to the general path;
  `AIL_UNIFIED_FORCE=1` forces the general path for a comparison.

`T` = typed (the typed path builds and matches CPython), `G` = general (the typed path refuses and
the general path builds it), `R` = refused by name (neither path builds it). A status in
parentheses names the path that refuses a program the other path builds.

## The 30 programs

| # | shape | before | after | CPython |
|---|-------|--------|-------|---------|
| h01 | single inheritance, base-typed list, overridden `sound()` | T | T | yes |
| h02 | three levels, `super().__init__` and `super().method()` | T | T | yes |
| h03 | `super().m()` plus `Sub.m(self, ...)` | G | G | yes |
| h04 | three shapes, override through `list[Shape]` | T | T | yes |
| h05 | `isinstance` and `issubclass`, including a mixed `(B, int)` / `(A, int)` spec | R | T (general refuses `issubclass`) | yes |
| h06 | class attributes inherited and shadowed, read through the class and `self` | T | T | yes |
| h07 | abstract-style `raise NotImplementedError`, base list holds only the concrete class | T | T | yes |
| h08 | abstract base constructed, `f()` raises, caught in `except NotImplementedError` | G | G | yes |
| h09 | override calls `super().f()`, catches its `NotImplementedError` | G | G | yes |
| h10 | multiple inheritance (`C(A, B)`) | R | R | not built |
| h11 | library base (`MyList(list)`, `MyDict(dict)`) | R | R | not built |
| h12 | method only the subclass has, called on the subclass then the base | G | G | yes |
| h13 | subclass without `__init__` uses the base's | T | T | yes |
| h14 | template method: base `run()` calls overridden `step()` | T | T | yes |
| h15 | inherited `@classmethod` constructor, overridden in a subclass | G | G | yes |
| h16 | inherited / overridden `@staticmethod` called through `self` | G | G | yes |
| h17 | `@property` getter/setter overridden in a subclass | G | G | **no**, prints `50` not `60` (pre-existing) |
| h18 | `super().__init__(x=..., y=...)` | T | T | yes |
| h19 | `super().m(*(a, b))` | R | R | not built (`*argument` in a call) |
| h20 | `type(x).__name__`, `isinstance` against a tuple of classes | G | G | yes |
| h21 | class attribute inherited, shadowed, and read by an inherited method | T | T | yes |
| h22 | instance attribute shadows a class attribute | T | T | yes |
| h23 | diamond multiple inheritance with explicit `Left.__init__` / `Right.__init__` | R | R | not built |
| h24 | user exception hierarchy with `super().__init__` and per-class fields | G | G | yes |
| h25 | abstract base type, concrete subclasses, mixed operations through a base list | T | T | yes |
| h26 | `abc.ABC` + `@abstractmethod`; constructing the base raises `TypeError` | G | G | **no**, the `abstract` line is missing (pre-existing A51) |
| h27 | `issubclass` across the hierarchy, tuples, `object` and builtin types | R | T (general refuses `issubclass`) | yes |
| h28 | base-typed parameter and base-typed return | T | T | yes |
| h29 | base-typed field holds a subclass, then the base | T | T | yes |
| h30 | class-variable counter through `Counted.count += 1` and `super().__init__` | G | G | yes |

Totals: before **13 typed / 11 general / 6 refused**; after **16 typed / 10 general / 4 refused**.
No program changed from typed or general to refused.

## The top refusal and the fix

The largest refusal group that uses the task's required features was the class test itself
(h05, h27): the typed path had no `issubclass` at all, and `isinstance(x, (B, int))` refused because
the tuple mixed a class of the program with a builtin type. Multiple inheritance (h10, h23) also
refused twice, but it is deliberately out of scope (the named refusal suggests holding the other
base as a field). The two class-test programs are now typed:

* `issubclass(C, D)` and `issubclass(C, (D1, D2, ...))` are folded when both sides are class names
  of the hierarchy, builtin type names, or `object`; the answer is a bool, so `print` shows
  `True` / `False`.
* `isinstance(x, (C, int, ...))` with at least one class of the hierarchy now reaches the existing
  class-id test; builtin targets that cannot match a class instance are false, and `object` is true
  (including for `None`, which is an instance of `object`) wherever it appears in the tuple, even
  after a class that already matches the value.
  The receiver keeps its existing requirement: a name or an attribute.
* A parameter or local that shadows a class or builtin type name is a value, not that class; the
  fold sees the shadow and refuses the class test (`isinstance` or `issubclass`) by name rather
  than printing an answer that CPython raises `TypeError` for. A user-defined `issubclass` (a
  `def`) is likewise not folded.

The general path still refuses `issubclass` by name (`the name 'issubclass' is not a known
function/class/builtin`) and refuses `isinstance(..., (C, object))` by name; the default build is
typed for these programs, so it matches CPython. Both come from the class-test lowering in
`python/pkg-v12/pyfunc.py` (`_mixed_class_isinstance`, `_static_issubclass`) and the bool spelling in
`boolkind.py`; `test_ail_class_reach.py` covers them.

## Still refused or general after the fix

* Multiple inheritance (h10, h23) and a library base (h11) keep their existing named refusals.
* A starred argument in `super().m(*(a, b))` (h19) is still refused by name.
* A tuple of class objects used as values (`for cls in (A, B, C)`) is still refused at the tuple
  display; only statically named class tests are folded.
* The general path carries properties/ABCs with its existing differences (h17, h26); these are
  pre-existing, not changed here.
* An abstract base that is constructed (h08) and a `super().m()` that raises (h09) still take the
  general path because the typed dispatcher treats a reachable stub as a refusal.
