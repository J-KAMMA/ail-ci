# DIFFERENCES

| id | area | difference |
|----|------|------------|
| C?-job-cov6-10220953-1 | ipaddress | `IPv4Address` is built; `IPv4Network`, `IPv4Interface`, `ip_address` and IPv6 are refused by name. |
| C?-job-cov6-10220953-2 | urllib.parse | The pure-Python functions listed in `stdlib6.py` are built; other names (for example `urldefrag`) are refused by name. |
Rows added by job-fuzz8-10220554 use the placeholder id form requested for this branch.

| id | status | area | description |
|---|---|---|---|
| C?-job-fuzz8-10220554-1 | open | itertools | `permutations` / `combinations` / `combinations_with_replacement` with a negative `r` return `[]` on the general path; CPython raises `ValueError: r must be non-negative`. |
| C?-job-fuzz8-10220554-2 | open | enumerate | `enumerate(xs, start)` with `None`, a float, a str or a list is accepted on the general path (None becomes 0, the others are read as a pointer-sized value) instead of raising `TypeError: '<type>' object cannot be interpreted as an integer`. |
| C?-job-fuzz8-10220554-3 | open | reversed | `reversed` of a dict, a dict view or a bytearray raises `TypeError: '<type>' object is not reversible` at run time; CPython 3.12 reverses all of them. |
| C?-job-fuzz8-10220554-4 | open | groupby | `print`/`repr` of an unread `groupby` grouper shows `<object>`; CPython shows `<itertools._grouper object at 0x...>` (the address cannot match byte for byte anyway). |
| C?-job-fuzz8-10220554-5 | open | nesting | On the general path `map` / `filter` / `zip` / `enumerate` over a library iterator (for example `map(f, itertools.accumulate(...))`) dies with `AIL internal error: iterator: unknown kind`; the core `AIL_IT_MAP`/`FILTER`/`ZIP`/`ENUMERATE` cases call the core dispatcher, not `ail_it_next`, for their source. |
| C?-job-fuzz8-10220554-6 | refused | zip_longest | More than two iterables (with or without `fillvalue=`) are refused by name by the default lowering, although CPython accepts them; `zip_longest(*[[1, 2], [3]])` is refused too. |
| C?-job-fuzz8-10220554-7 | refused | starmap | A callable that is not exactly two arguments (a 1- or 3-argument def, `pow` with triples) is refused by name; CPython calls it with every tuple element. |
| C?-job-fuzz8-10220554-8 | refused | zip | `zip(..., strict=True)` is refused by name when there are more than two iterables. |
