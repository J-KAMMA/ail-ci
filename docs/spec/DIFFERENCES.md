# Differences from CPython 3.12

This CI export does not carry the full development ledger.  The row closed by this job is kept here
so the change is recorded with the code it describes.

| id | status | difference |
| --- | --- | --- |
| C169 | closed | `list.index` / `tuple.index` read a `None`, float or str bound as index 0 instead of raising CPython's `TypeError: slice indices must be integers or have an __index__ method`.  Both bounds are now converted at run time (int / bool / `__index__`); a bad `__index__` return is CPython's `__index__ returned non-int (type ...)`.  Covered by `test_ail_c169.py`. |
