# DEVLOG

## 2026-10-21 - docs1: user reference audited against the compiler

- Ran every runnable reference example (`AIL_REFERENCE.md`, `AIL_REFERENCE_MORE.md`) with the
  default build and the general path; the python examples were also compared with CPython 3.12.
  All 16 runnable examples build and print what the document states.
- Removed stale limits and documented lifted features: `with` / `contextlib`, csv, `Flag` /
  `IntFlag`, `@dataclass` inheritance, `re.subn` and function replacements, `print(*xs)` /
  `Cls(*xs)`, `zip` in a `for`, dict comprehensions, `isinstance`, `min` / `max` with `key=`,
  `int | None` / `float | None` / `str | None`, `with open(...)` + `f.write`, and the string
  methods `partition`, `ljust`, `rjust`, `center`.
- Kept the core card at 3499 bytes and rebuilt the MORE line index with `tools/ref_index.py`.
- `docs/spec/DIFFERENCES.md` is not part of this public export, so no new DIFFERENCES row was
  added; the docs changes declare the typed-path / general-path split in place.
