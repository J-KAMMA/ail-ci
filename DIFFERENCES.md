# Differences from CPython

Rows here record a deliberate or still-open difference. A silent wrong answer is a bug; a named
compile-time refusal is acceptable. New rows from this branch use the placeholder id
`C?-job-fuzz3-10220508-N` until the export assigns the real number.

| id | area | CPython | AIL before | status |
| --- | --- | --- | --- | --- |
| C?-job-fuzz3-10220508-1 | `str.find` / `rfind` / `index` / `rindex` / `count` / `startswith` / `endswith` with `start`/`end` (general path) | an inverted window or a `start` past the end searches nothing: `"aXbXc".find("", 10, 0)` is `-1`, `"abc".find("", 4)` is `-1` | `ail__win` clamped `start` down to `len` and collapsed an inverted window into the valid empty window at that start, so the same calls returned `5` and `3` | fixed: `ail__win` returns whether the window is valid, never clamps `start` above `len`, and its callers answer `-1` / `0` / `False` / `ValueError` for an invalid window |
