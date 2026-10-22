## 2026-10-22 — IntEnum / IntFlag review fixes (branch job-intenum4-10221632)

- 3-argument `pow()`: a float anywhere keeps the int-only message; without a float, a non-index operand
  names the original operands (`'C', 'E', 'int'`), after any `IntEnum` / `IntFlag` `__index__` conversion.
- `divmod()` now dispatches only through `__divmod__` / `__rdivmod__`, converts an `IntEnum` / `IntFlag`
  operand through `__index__`, names the original classes in the `TypeError`, and keeps `float divmod()` /
  `integer division or modulo by zero` for zero divisors. `__floordiv__` / `__mod__` alone no longer fake it.
- Plain `Enum` equality returns `NotImplemented` across classes so the other operand's `__eq__` runs; plain
  enum ordering names both classes and the actual operator (`<`, `<=`, `>`, `>=`). Custom ordering now also
  raises the operator-specific `TypeError` instead of borrowing `__lt__` for `<=` / `>=`.
- Added the review cases to `AIL_CURRENT/test_ail_intenum4.py` (both directions, float/int zero, user
  `__divmod__` / `__rdivmod__` / `NotImplemented`, values through parameters, lists, attributes and dicts).

# Dev log

## 2026-10-21 — IntEnum / IntFlag leftovers (branch job-intenum4-10220559)

- `_AilIntEnum` now defines `__pow__` / `__rpow__`; the 3-argument `pow()` converts an enum operand
  through `__index__` on the general path. Negative and zero exponents, aliases, IntFlag composites and
  values reached through arguments, list items, attributes and dict values match CPython.
- Equality is by value only between int-like enum members: an `IntEnum` / `IntFlag` member is no longer
  equal to a plain `Enum` / `Flag` member with the same value (both directions); `StrEnum` follows the
  same rule against another `StrEnum`, not against a plain `Enum`. Arithmetic / ordering against a plain
  enum member now raises rather than computing a value.
- Int `% 0` text changed to CPython 3.12's "integer modulo by zero"; `//` / `divmod(int, 0)` keep the
  old "integer division or modulo by zero". Float `divmod(x, 0)` says "float divmod()" in the general
  `ail_bi_divmod` path and the typed `_ail_divmod_f` helper.
- Added `AIL_CURRENT/test_ail_intenum4.py`: exponentiation, cross-kind equality/arithmetic, and the
  division-by-zero spellings on the general path, the default build (IR 0 and 1), and the typed path
  for the divmod helper.
