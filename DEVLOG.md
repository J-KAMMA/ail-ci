# AIL development log

## 2026-10-22 — job-fuzz17 review fixes

Review of `2aed49e` found three defects, all fixed:

- `@dataclass(eq=False)` keeps the `__hash__` CPython would: its own `__hash__` (including `= None` and an
  assigned lambda/function), `None` when it defines `__eq__`, an inherited base hash, or an id-based
  identity hash only when the answer is `object.__hash__` (no constant hash, so distinct live instances no
  longer collide). Inherited fieldless dataclasses follow the same rule.
- an inline (`class E: pass`) or tab-indented empty `@dataclass` keeps the real class indentation (the
  decorator column, not the column after the colon); an inline suite is made into a block first, so repr,
  equality and `__doc__` agree with CPython.
- enum member writes are refused by name for tuple/list and nested targets, `for` / `with` targets,
  comprehensions, annotated targets and `setattr(E.A, "value" | "name", ...)`, not only a lone attribute.

Probes in `/tmp/rprobes` (reviewer set) and `/tmp/probes` (fresh `q17_*` programs) cover both builds.
Required tests pass on the final commit.


## 2026-10-22 — job-fuzz17: dataclasses and enums

Differential fuzzing (99 small programs, both builds) against CPython 3.12 found these silent wrong answers,
now fixed on branch `job-fuzz17-10220947`:

- a `@dataclass` with no fields of its own now gets the generated `__init__`, `__eq__` and repr;
- a `@dataclass(eq=False)` keeps object identity and is hashable again (constant identity-valid `__hash__`);
- an Enum aliases equal values (`0` / `False`, `1` / `1.0` / `True`), `__members__` keeps definition order,
  and `@unique` with a duplicate is refused by name;
- writing `E.A.value` / `E.A.name` is refused by name instead of mutating the member.

Remaining differences are listed in `DIFFERENCES.md`.
