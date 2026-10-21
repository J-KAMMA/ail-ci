# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-fuzz4-10220602-1 | dict methods | `pop`/`setdefault` call `__hash__` once (including the empty-dict `pop` fast path); `update(other_dict)`, `copy`, `popitem` and `dict(d)` reuse stored hashes instead of hashing again. | fixed 2026-10-21 |
| C?-job-fuzz4-10220602-2 | dict/set literals | On the general path every key/value/element expression is evaluated before any key is hashed, as CPython 3.12 `BUILD_MAP`/`BUILD_SET` do; an unhashable early key no longer hides later side effects. The typed path has no user `__hash__` keys. | fixed 2026-10-21 |
| C?-job-fuzz4-10220602-3 | dict iteration | Same-size delete+reinsert during live iteration can stop on the typed path where CPython continues, or continue on the general path where CPython raises "dictionary keys changed during iteration"; the declared rule is in SEMANTICS section 240. | open |
| C?-job-fuzz4-10220602-4 | dict construction | `dict(d)` may call a user `__eq__` a different number of times than CPython when `d`'s key table has a shape CPython can share; the values and order are the same. | open |
| C?-job-fuzz4-10220602-5 | dict operators | `reversed(d)` and `d1 | d2` compile and then stop with a runtime TypeError instead of working or being refused by name. | open |
