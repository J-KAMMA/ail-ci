# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre17-10240052-1 | Counter equality | the general path compared two Counters as dicts: the whole-mapping identity shortcut made `c == c` True for a NaN count, and a missing/zero count compared unequal | fixed: both builds use Counter.__eq__ (counts with `==`, missing counts zero) |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
