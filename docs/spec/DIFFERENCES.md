# Differences from CPython 3.12

This CI export does not carry the full development ledger.  The row closed by this job is kept here
so the change is recorded with the code it describes.

| id | status | difference |
| --- | --- | --- |
| C169 | closed | `list.index` / `tuple.index` read a `None`, float or str bound as index 0 instead of raising CPython's `TypeError: slice indices must be integers or have an __index__ method`.  Both bounds are now converted at run time (int / bool / `__index__`); the typed lowering handles visible int/bool and non-index bounds and leaves the rest to that path, and a bad `__index__` return is CPython's `__index__ returned non-int (type ...)` with the complete type name.  Covered by `test_ail_c169.py`. |
# Differences from CPython

New rows found by the fuzz jobs use the placeholder id `C?-<branch>-N`.

| id | area | difference |
|----|------|------------|
| C?-job-fuzz21-10230420-1 | integers | An integer literal/expression beyond 64 bits (for example `10**50`) traps with `integer overflow` on both builds; CPython prints the value. This is outside unpacking, which the same probe otherwise matches. |
# Differences from CPython

This export carries the rows found by the jobs run here; the full list is maintained upstream.

| id | area | difference |
|---|---|---|
| C?-job-fuzz70-10231500-1 | assert | A typed-only (`--strict` / `AIL_NO_GENERAL=1`) build refuses `assert cond, tuple_message` by name. The default build and the general path keep the message object in `AssertionError.args`, as CPython does. |
| id | difference |
| --- | --- |
| C?-job-fuzz82-10231553-1 | A function that deletes an item of a module-level numeric list (`del xs[i]`) is refused by name on the typed path. Before, deleting the last item printed the unchanged list (the write through the `const` table was dropped) and deleting an earlier item crashed; the default build falls back to the general path and matches CPython. |
