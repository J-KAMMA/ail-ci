# Differences from CPython 3.12

This CI export does not carry the full development ledger.  The rows closed by these jobs are kept here
so the changes are recorded with the code they describe.

| id | status | area | difference |
| --- | --- | --- | --- |
| C169 | closed | list/tuple index | `list.index` / `tuple.index` read a `None`, float or str bound as index 0 instead of raising CPython's `TypeError: slice indices must be integers or have an __index__ method`.  Both bounds are now converted at run time (int / bool / `__index__`); the typed lowering handles visible int/bool and non-index bounds and leaves the rest to that path, and a bad `__index__` return is CPython's `__index__ returned non-int (type ...)` with the complete type name.  Covered by `test_ail_c169.py`. |
| C170 | closed | ipaddress | `IPv4Address` is built; `IPv4Network`, `IPv4Interface`, `ip_address` and IPv6 are refused by name. |
| C171 | closed | urllib.parse | The pure-Python functions listed in `stdlib6.py` are built; other names (for example `urldefrag`) are refused by name. |
| C172 | closed | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) |
