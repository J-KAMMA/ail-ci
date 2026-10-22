# AIL development log

## 2026-10-22 — job-fuzz17: dataclasses and enums

Differential fuzzing (99 small programs, both builds) against CPython 3.12 found these silent wrong answers,
now fixed on branch `job-fuzz17-10220947`:

- a `@dataclass` with no fields of its own now gets the generated `__init__`, `__eq__` and repr;
- a `@dataclass(eq=False)` keeps object identity and is hashable again (constant identity-valid `__hash__`);
- an Enum aliases equal values (`0` / `False`, `1` / `1.0` / `True`), `__members__` keeps definition order,
  and `@unique` with a duplicate is refused by name;
- writing `E.A.value` / `E.A.name` is refused by name instead of mutating the member.

Remaining differences are listed in `DIFFERENCES.md`.
