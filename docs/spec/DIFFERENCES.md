# Differences from CPython 3.12

This CI export does not carry the full development ledger.  The row closed by this job is kept here
so the change is recorded with the code it describes.

| id | status | difference |
| --- | --- | --- |
| C169 | closed | `list.index` / `tuple.index` read a `None`, float or str bound as index 0 instead of raising CPython's `TypeError: slice indices must be integers or have an __index__ method`.  Both bounds are now converted at run time (int / bool / `__index__`); the typed lowering handles visible int/bool and non-index bounds and leaves the rest to that path, and a bad `__index__` return is CPython's `__index__ returned non-int (type ...)` with the complete type name.  Covered by `test_ail_c169.py`. |
| C?-job-cov8-10240949-1 | closed | The typed path refused every `random.Random` method with defaults (`Random.randrange must take plain positional arguments...`), so 10 gdev programs fell back to the general path.  The typed prelude now provides the one- and three-argument `randrange` spellings (`randrange1` / `randrange3`) and `randlib.py` rewrites calls on a proven `Random`; a method call whose signature is unavailable while class shapes are scanned is refused by name instead of raising `KeyError`.  Covered by `test_ail_cov8.py`. |
# Differences from CPython

New rows found by the fuzz jobs use the placeholder id `C?-<branch>-N`.

| id | area | difference |
|----|------|------------|
| C?-job-fuzz21-10230420-1 | integers | An integer literal/expression beyond 64 bits (for example `10**50`) traps with `integer overflow` on both builds; CPython prints the value. This is outside unpacking, which the same probe otherwise matches. |
