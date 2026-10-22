# DIFFERENCES

| id | area | difference |
|----|------|------------|
| C170 | ipaddress | `IPv4Address` is built; `IPv4Network`, `IPv4Interface`, `ip_address` and IPv6 are refused by name. |
| C171 | urllib.parse | The pure-Python functions listed in `stdlib6.py` are built; other names (for example `urldefrag`) are refused by name. |
Rows added by job-fuzz8-10220554 use the placeholder id form requested for this branch.

| id | status | area | description |
|---|---|---|---|
| C172 | open | itertools | `permutations` / `combinations` / `combinations_with_replacement` with a negative `r` return `[]` on the general path; CPython raises `ValueError: r must be non-negative`. |
| C173 | open | enumerate | `enumerate(xs, start)` with `None`, a float, a str or a list is accepted on the general path (None becomes 0, the others are read as a pointer-sized value) instead of raising `TypeError: '<type>' object cannot be interpreted as an integer`. |
| C174 | open | reversed | `reversed` of a dict, a dict view or a bytearray raises `TypeError: '<type>' object is not reversible` at run time; CPython 3.12 reverses all of them. |
| C175 | open | groupby | `print`/`repr` of an unread `groupby` grouper shows `<object>`; CPython shows `<itertools._grouper object at 0x...>` (the address cannot match byte for byte anyway). |
| C176 | open | nesting | On the general path `map` / `filter` / `zip` / `enumerate` over a library iterator (for example `map(f, itertools.accumulate(...))`) dies with `AIL internal error: iterator: unknown kind`; the core `AIL_IT_MAP`/`FILTER`/`ZIP`/`ENUMERATE` cases call the core dispatcher, not `ail_it_next`, for their source. |
| C177 | refused | zip_longest | More than two iterables (with or without `fillvalue=`) are refused by name by the default lowering, although CPython accepts them; `zip_longest(*[[1, 2], [3]])` is refused too. |
| C178 | refused | starmap | A callable that is not exactly two arguments (a 1- or 3-argument def, `pow` with triples) is refused by name; CPython calls it with every tuple element. |
| C179 | refused | zip | `zip(..., strict=True)` is refused by name when there are more than two iterables. |
| C180 | refused | accumulate | On the typed path `itertools.accumulate(xs, initial=v)` is refused by name when `v` has a different type from the elements (for example one-argument `round()` is an `int` over a `list[float]`); the default build falls back to the general path, which matches CPython. |
| C181 | open | groupby | With mutable elements (for example `list[list[int]]`) the typed path cannot lower the key look-ahead yet: `--strict` refuses it (`'_ilN_gc' is read before it is assigned`), so the default build falls back to the general path, which matches CPython. Keys over scalar/str element lists stay on the typed path and are called once per element. |
# Differences from CPython 3.12

Rows found while closing the IntEnum / IntFlag leftovers on branch `job-intenum4-10220559`. The ids are
placeholders until the maintainer assigns the final C-series numbers.

| id | area | difference | status |
| --- | --- | --- | --- |
| C182 | `pow(base, exp, mod)` | A float in any position keeps CPython's `pow() 3rd argument not allowed unless all arguments are integers` (a plain Enum on another position no longer turns that into an operand-name error). With no float, a non-index operand (a plain `Enum`, `str`, ...) names the three original operands, e.g. `'C', 'E', 'int'`, not the int an `IntEnum` was converted to. | fixed |
| C183 | `divmod()` | `divmod()` asks only `__divmod__` / `__rdivmod__` (never `__floordiv__` / `__mod__`); `_AilIntEnum` defines both for int, float and IntEnum operands, while a plain class with only `__index__` is not converted. Its `TypeError` names the original classes (`'E' and 'C'`), a zero divisor with a float operand says `float divmod()`, and `divmod(int, 0)` says `integer division or modulo by zero`. | fixed |
| C184 | `enum.Enum` | A plain `Enum` member on the left defers to the other operand's `__eq__` (returning `NotImplemented` across classes), so an overridden `IntEnum.__eq__` runs. Ordering a plain `Enum` names both classes and the actual operator (`<=`, `>`, ...), not `'instance'` and `'<'`; against a non-enum operand it returns `NotImplemented`, so a custom reflected comparison runs and a failure names both classes (`'E' and 'int'`). | fixed |
| C185 | `enum.IntEnum` / `enum.IntFlag` | `member ** n`, `n ** member`, member-to-member `**`, `pow(member, n)`, `pow(n, member)` and the 3-argument `pow(member, n, mod)` now give the int result (the member is an int subclass in CPython). `__pow__` / `__rpow__` were missing from `_AilIntEnum`; the general runtime now converts an instance operand of the 3-argument `pow()` through `__index__`. | fixed |
| C186 | `enum.IntEnum` / `enum.IntFlag` / `enum.StrEnum` | A member no longer compares equal to a plain `Enum` / `Flag` member that happens to have the same value: a plain enum member is an object, and CPython's `Enum.__eq__` is identity. Another `IntEnum` / `IntFlag` member (also from a different class), an `int`, a `float` and a `bool` still compare by value; a `StrEnum` compares by its string value with another `StrEnum` / `str`. Arithmetic and ordering with a plain enum member now raise CPython's `TypeError` instead of returning a numeric result. | fixed |
| C187 | arithmetic | `5 % 0` now says `ZeroDivisionError: integer modulo by zero` (was "integer division or modulo by zero"). Int `// 0` and `divmod(int, 0)` keep "integer division or modulo by zero"; float `%` / `//` keep "float modulo" / "float floor division by zero"; `divmod` with a float operand and a zero divisor now says "float divmod()" on the general and typed paths. | fixed |
