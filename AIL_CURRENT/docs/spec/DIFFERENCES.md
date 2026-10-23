# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre17-10240052-1 | Counter equality | the general path compared two Counters as dicts: the whole-mapping identity shortcut made `c == c` True for a NaN count, and a missing/zero count compared unequal; a first fix then compared counts with raw equality only, so identity-based counts (function/class/range/instance) became unequal to themselves in untyped contexts, and a self-referential count overflowed the C stack | fixed: both builds use Counter.__eq__ (counts with `==`, an identity fallback for non-float values, missing counts zero), and a cyclic count traps `recursion depth exceeded` like CPython's RecursionError |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
