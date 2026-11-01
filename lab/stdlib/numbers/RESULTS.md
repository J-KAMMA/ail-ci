# numbers: real-program coverage

Twelve programs in this directory use `numbers` the way ordinary code does: the five ABCs
(`Number`, `Complex`, `Real`, `Rational`, `Integral`), `isinstance` and `issubclass`, tuples of
types, registration with `register` (both the call and decorator forms), classes that inherit an
ABC, Fraction / Decimal classification, arithmetic results, and caught `TypeError` /
`ValueError` edge cases including empty inputs. Each is 17-49 lines and is built with

    AIL_CURRENT/ail_chatgpt.py compile <file>.py --syntax python

## Result

Eleven of the twelve build in the default mode and match CPython 3.12 stdout and exit code.
All eleven are built on the **general** path: the injected ABC classes carry operator methods
(`Complex.__bool__`, `Real.conjugate`, ...), so the typed path declines and the default build
falls back to the general runtime.

| # | program | result | CPython stdout + exit |
| --- | --- | --- | --- |
| 1 | `averages.py` | general | match |
| 2 | `classify.py` | general | match |
| 3 | `custom_number.py` | general | match |
| 4 | `dispatch.py` | general | match |
| 5 | `issubclass_report.py` | general | match |
| 6 | `matrix_stats.py` | general | match |
| 7 | `mixed_registry.py` | general | match |
| 8 | `number_guard.py` | general | match |
| 9 | `rationals.py` | general | match |
| 10 | `registration.py` | general | match |
| 11 | `result_kinds.py` | general | match |
| 12 | `complex_literal.py` | refused | not built (complex values) |

Before the fixes, `import numbers` was not modelled at all: the first probe stopped at
`not in the subset: isinstance() with a non-name type argument`, a plain `numbers.Integral`
read stopped at `not in the subset: numbers.Integral used as a plain value`, and `issubclass`
was `not in the subset: the name 'issubclass' is not a known function/class/builtin`.

The first build with the new `numbers` lowering still refused two programs whose mixed
`isinstance` tuple began with a constructor call (the lowering needed a plain name to evaluate
the value once); splitting that value into a local let the ordinary mixed tuple path build them.
The `custom_number.py` and `dispatch.py` sources also had their own print/arithmetic defects at
that point (an object repr and a `Celsius - Celsius` call), which were corrected before the final
comparison. No refusal remains for those features.

## Fixes

* `python/pkg-v12/prelude_numbers.py` (new): the five ABCs as plain classes in CPython's
  inheritance order, with the concrete methods ordinary subclasses inherit (`real`, `imag`,
  `conjugate`, `__index__`, `__float__`, `numerator`, `denominator`).
* `python/pkg-v12/numberslib.py` (new): the source pass called from `stdlib5`. It removes the
  imports, lowers `isinstance` to `_ail_num_isinstance(x, kind)` (or `_ail_num_in(x, [kinds])`
  for tuples), and classifies bool/int as `Integral`, float as `Real`, complex as `Complex`,
  Fraction as `Rational` and Decimal as `Number`. `issubclass` is answered statically for the
  builtin types, the ABCs, Fraction/Decimal and classes defined in the program (including
  `issubclass(type(x), ABC)`); `numbers.X.register(Cls)` and `@numbers.X.register` record the
  class in a run-time virtual-registration table and return that class, as CPython's `register`
  does. The registration runs where it is written (inside a function, under `if`, or at module
  scope) and does not add a base, so a registered class does not inherit the ABC's `real`,
  `imag` or `conjugate` methods. The runtime classifier tests the actual injected `Fraction` / `Decimal`
  classes when those modules are imported, so a subclass of `fractions.Fraction` is a
  Rational/Real/Number and a user class that merely has the same name is not one. `isinstance`
  tuples are flattened recursively; a tuple with no `numbers.*` element is left to the ordinary
  `isinstance`, and a `numbers` class used as a plain value is refused by name.
* `python/pkg-v12/stdlib5.py` and `ail_syntax.py`: `numbers` joined the batch-5 word list and
  the surface gate, so the pass runs before the other source passes.

## Follow-ups

* **Complex values are not built.** `complex_literal.py` is refused with

      not in the subset: dunder method Complex.__bool__; only __init__ is supported here, no other dunder (__eq__, __repr__, __len__, __add__, ...) (the general path could not build this program either); general path: a constant of type complex

  Building complex literals / `complex()` / complex arithmetic is a larger new feature.
* **ABCMeta's abstract-method check is not modelled.** CPython refuses to instantiate a
  subclass that leaves abstract methods unimplemented (`TypeError: Can't instantiate abstract
  class ...`); here the class can be instantiated. A complete subclass matches CPython.
* **A run-time class value in `issubclass` is refused by name.** Only a class named in the
  program, a builtin type, the ABCs or `type(x)` is classified; for example
  `issubclass(type(x).__class__, numbers.Number)` is refused (the generic first line comes from
  the unlowered `issubclass`, followed by the naming note):

      not in the subset: the name 'issubclass' is not a known function/class/builtin
      note: <file>:<line>: issubclass() of a class value that is not a name defined in this program is not built; write issubclass(type(x), numbers.X) or a class defined here

* **A register call written before its class definition is refused by name**, because the
  compiler binds a class name statically and CPython would raise `NameError` there; move the
  registration after the class definition. A register decorator combined with another decorator
  is also refused by name (the decorator order could change which class object is registered).
* **A parameter that shadows a from-imported ABC name is refused by name**, matching the
  existing refusal for a def or class with that name.

No other feature is needed for the eleven passing programs.
