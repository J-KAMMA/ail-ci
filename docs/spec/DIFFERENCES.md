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
| id | status | area | summary |
| --- | --- | --- | --- |
| C?-job-fuzz61-10231419-1 | fixed | string encoding | A run-time encoding name used to accept only a few spellings of utf-8, ascii and latin-1, so aliases reached through a variable, argument, list item, attribute or dict value raised `LookupError`. Every alias from `encodings.aliases` for those three codecs is now accepted on both builds. |
| C?-job-fuzz61-10231419-2 | open | string encoding | A run-time name of a codec outside utf-8/ascii/latin-1 (for example `cp1252`, `utf-8-sig`, `utf-16`) raises `LookupError` where CPython encodes or decodes. The same name written as a literal is refused at compile time by name. |
| C?-job-fuzz61-10231419-3 | open | string encoding | `b"".decode(name)` looks the codec up and raises `LookupError` for an unknown name; CPython returns `b""` without looking it up. `"".encode(name)` does validate the name in both. |
| C?-job-fuzz61-10231419-4 | open | exceptions | `UnicodeEncodeError` / `UnicodeDecodeError` values do not expose `.encoding`, `.object`, `.start`, `.end` or `.reason`. |
