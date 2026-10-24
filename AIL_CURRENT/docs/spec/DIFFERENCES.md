# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre51-10241239-1 | format() spec errors | A space sign on a str printed "Sign not allowed..." instead of CPython's "Space not allowed..."; an invalid spec omitted the spec and value type (for example `' +8'` for an int); an unknown format code printed the raw control/space/non-ASCII character instead of CPython's `\xNN`. The general path now produces CPython's wording; the float `z` flag already matched. `test_ail_pre51.py` keeps the cases. | fixed |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
# Differences from CPython 3.12

Rows are behaviours where this compiler deliberately differs from CPython, or
behaviours it refuses by name. New ids from worker branches use the placeholder
form `C?-<branch>-N`.

| id | area | difference |
| --- | --- | --- |
| C?-job-fuzz51-10231205-1 | bytes/bytearray padding | `ljust`, `rjust` and `center` with an explicit `None` fillchar now raise CPython's TypeError instead of silently padding with spaces. This is a fixed silent difference; `test_ail_fuzz51.py` keeps the case. |
| C?-job-fuzz37-10230931-1 | ordering comparisons | A TypeError from `<`, `<=`, `>`, `>=` on built-in values that cannot be ordered now names the operator that was written, as CPython does, instead of always naming `<`. This is not a deliberate difference; the row records the fixed behaviour and the fuzz37 regression test. |
