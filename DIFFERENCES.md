# Known differences

Rows added by job-fuzz17-10220947 (placeholder ids; renumber on merge).

| id | area | difference |
| --- | --- | --- |
| C?-job-fuzz17-10220947-1 | dataclass frozen | assigning a field of a frozen dataclass is not refused; CPython raises FrozenInstanceError |
| C?-job-fuzz17-10220947-2 | Enum membership | `1 in E` is False; CPython 3.12 answers by value |
| C?-job-fuzz17-10220947-3 | Enum aliases | a value that is an equal constant expression (`B = 1 + 0`) is not treated as an alias |
| C?-job-fuzz17-10220947-4 | Enum class str/repr | `str(E)` / `repr(E)` show the member list instead of `<enum 'E'>` |
| C?-job-fuzz17-10220947-5 | Enum errors | `E(1)` on an empty enum raises ValueError; CPython raises TypeError |
| C?-job-fuzz17-10220947-6 | dataclass attributes | instances have no `__dict__` / `vars()`, and a bound method stored in a variable cannot be called |
| C?-job-fuzz17-10220947-7 | StrEnum | a member is not usable as a str (`S.A[0]`) |
| C?-job-fuzz17-10220947-8 | exception text | TypeError names the class `instance`, not the class name |
| C?-job-fuzz17-10220947-9 | tuple ordering | comparing tuples holding None raises TypeError where CPython can order them |
| C?-job-fuzz17-10220947-10 | object repr |  a class without `__repr__` prints `<R object>` without the module and address |
| C?-job-fuzz17-10220947-11 | class `__doc__` | `X.__doc__` on a plain or dataclass class raises AttributeError instead of returning its docstring |
| C?-job-fuzz17-10220947-12 | `@dataclass(order=True, eq=False)` | the class is built (and compares) where CPython raises `ValueError: eq must be true if order is true` |
| C?-job-fuzz17-10220947-13 | IntEnum values | an IntEnum member declared with a float value (`C = 2.0`) keeps `2.0` in repr; CPython stores the coerced int `2` |
