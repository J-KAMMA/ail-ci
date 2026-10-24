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
| C?-job-fuzz21-10230420-1 | integers | A statically known integer constant expression beyond 64 bits (for example `10**50` or `MAX * 2`) is now refused at compile time by name (`int64 constant expression out of range: ...`) on both builds; a value that only reaches the operation at run time still traps with `integer overflow`. CPython prints the value. This is outside unpacking, which the same probe otherwise matches. |
# Differences from CPython

This export carries the rows found by the jobs run here; the full list is maintained upstream.

| id | area | difference |
|---|---|---|
| C?-job-fuzz70-10231500-1 | assert | A typed-only (`--strict` / `AIL_NO_GENERAL=1`) build refuses `assert cond, tuple_message` by name. The default build and the general path keep the message object in `AssertionError.args`, as CPython does. |
| id | difference |
| --- | --- |
| C?-job-fuzz82-10231553-1 | A function that deletes an item of a module-level numeric list (`del xs[i]`) is refused by name on the typed path. Before, deleting the last item printed the unchanged list (the write through the `const` table was dropped) and deleting an earlier item crashed; the default build falls back to the general path and matches CPython. |
| id | status | area | summary |
| --- | --- | --- | --- |
| C?-job-fuzz61-10231419-1 | fixed | string encoding | A run-time encoding name used to accept only a few spellings of utf-8, ascii and latin-1, so aliases reached through a variable, argument, list item, attribute or dict value raised `LookupError`. Every alias from `encodings.aliases` for those three codecs is now accepted on both builds. |
| C?-job-fuzz61-10231419-2 | open | string encoding | A run-time name of a codec outside utf-8/ascii/latin-1 (for example `cp1252`, `utf-8-sig`, `utf-16`) raises `LookupError` where CPython encodes or decodes. The same name written as a literal is refused at compile time by name. |
| C?-job-fuzz61-10231419-3 | open | string encoding | `b"".decode(name)` looks the codec up and raises `LookupError` for an unknown name; CPython returns `b""` without looking it up. `"".encode(name)` does validate the name in both. |
| C?-job-fuzz61-10231419-4 | open | exceptions | `UnicodeEncodeError` / `UnicodeDecodeError` values do not expose `.encoding`, `.object`, `.start`, `.end` or `.reason`. |
