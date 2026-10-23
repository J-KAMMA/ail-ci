# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre16-10240050-1 | Counter ordering | `Counter < <= > >=` raised TypeError because the two Counters reached the plain dict comparison; CPython compares every key of both operands with a missing count read as 0 (`<=`/`>=` subset/superset, `<`/`>` proper forms) | fixed: the general path compares Counters that way, also with zero, negative, float and NaN counts; the typed path still refuses collection ordering by name, so the default build uses the general path (`test_ail_pre16.py`) |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
