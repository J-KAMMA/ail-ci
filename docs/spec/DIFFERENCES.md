# Differences from CPython

This export carries the rows found by the jobs run here; the full list is maintained upstream.

| id | area | difference |
|---|---|---|
| C?-job-fuzz70-10231500-1 | assert | A typed-only (`--strict` / `AIL_NO_GENERAL=1`) build refuses `assert cond, tuple_message` by name. The default build and the general path keep the message object in `AssertionError.args`, as CPython does. |
