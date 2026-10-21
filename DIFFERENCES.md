# Differences from CPython

AIL aims to match CPython. Every row below names one place where it does not.
`closed` rows were bugs that have been fixed and are kept for the record; `open`
rows are still true. A new row gets the placeholder id `C?-<branch>-N` until the
coordinator assigns a number.

| id | status | subject | behaviour |
|----|--------|---------|-----------|
| C168 | closed | `str.find`/`rfind`/`count`/`startswith`/`endswith`/`index`/`rindex` with a `None` start or end | The general path treated a supplied `None` bound as a present bound with index 0, i.e. an empty window: `"hello".find("l", None, None)` gave -1 where CPython gives 2, and the same held for every method in the family and for a `None` that arrived through a variable, a function argument, a list item, a dict value or an attribute. The emitter (`AIL_CURRENT/python/pkg-v12/pyboxed2.py`) now tests each supplied bound's tag and passes `has_lo = 0` / `has_hi = 0` for a `None`, matching CPython and the typed path. |
| C?-job-fuzz3n-10220658-1 | open | `list.index` / `tuple.index` with a `None` start or end | CPython raises `TypeError: slice indices must be integers or have an __index__ method`; the general path reads the `None` as index 0. Not touched by the C168 change, which deliberately leaves the list/tuple branch of `_m_index` as it was. |
