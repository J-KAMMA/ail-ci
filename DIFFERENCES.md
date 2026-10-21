# Differences from CPython 3.12

Rows found while closing the IntEnum / IntFlag leftovers on branch `job-intenum4-10220559`. The ids are
placeholders until the maintainer assigns the final C-series numbers.

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-intenum4-10220559-1 | `enum.IntEnum` / `enum.IntFlag` | `member ** n`, `n ** member`, member-to-member `**`, `pow(member, n)`, `pow(n, member)` and the 3-argument `pow(member, n, mod)` now give the int result (the member is an int subclass in CPython). `__pow__` / `__rpow__` were missing from `_AilIntEnum`; the general runtime now converts an instance operand of the 3-argument `pow()` through `__index__`. | fixed |
| C?-job-intenum4-10220559-2 | `enum.IntEnum` / `enum.IntFlag` / `enum.StrEnum` | A member no longer compares equal to a plain `Enum` / `Flag` member that happens to have the same value: a plain enum member is an object, and CPython's `Enum.__eq__` is identity. Another `IntEnum` / `IntFlag` member (also from a different class), an `int`, a `float` and a `bool` still compare by value; a `StrEnum` compares by its string value with another `StrEnum` / `str`. Arithmetic and ordering with a plain enum member now raise CPython's `TypeError` instead of returning a numeric result. | fixed |
| C?-job-intenum4-10220559-3 | arithmetic | `5 % 0` now says `ZeroDivisionError: integer modulo by zero` (was "integer division or modulo by zero"). Int `// 0` and `divmod(int, 0)` keep "integer division or modulo by zero"; float `%` / `//` keep "float modulo" / "float floor division by zero"; `divmod` with a float operand and a zero divisor now says "float divmod()" on the general and typed paths. | fixed |
