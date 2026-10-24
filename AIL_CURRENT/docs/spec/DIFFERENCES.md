# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre26-10240859-1 | exception arguments | `repr(e.args[i])` on the typed path quoted numeric, bool and None arguments (`'3.0'` instead of `3.0`); `repr`, `!r` and `%r` now format the stored argument. | fixed |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
# Differences from CPython 3.12

Rows are behaviours where this compiler deliberately differs from CPython, or
behaviours it refuses by name. New ids from worker branches use the placeholder
form `C?-<branch>-N`.

| id | area | difference |
| --- | --- | --- |
| C?-job-fuzz51-10231205-1 | bytes/bytearray padding | `ljust`, `rjust` and `center` with an explicit `None` fillchar now raise CPython's TypeError instead of silently padding with spaces. This is a fixed silent difference; `test_ail_fuzz51.py` keeps the case. |
| C?-job-fuzz37-10230931-1 | ordering comparisons | A TypeError from `<`, `<=`, `>`, `>=` on built-in values that cannot be ordered now names the operator that was written, as CPython does, instead of always naming `<`. This is not a deliberate difference; the row records the fixed behaviour and the fuzz37 regression test. |
| C?-job-pre22-10240312-1 | with / generators | a `with` whose body yields in the same function was built, but closing that generator never reached `__exit__` (CPython passes `GeneratorExit`) | refused by name at compile time (`with` around a `yield`) |
