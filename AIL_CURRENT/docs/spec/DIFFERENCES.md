# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
# Differences from CPython 3.12

Rows are behaviours where this compiler deliberately differs from CPython, or
behaviours it refuses by name. New ids from worker branches use the placeholder
form `C?-<branch>-N`.

| id | area | difference |
| --- | --- | --- |
| C?-job-fuzz51-10231205-1 | bytes/bytearray padding | `ljust`, `rjust` and `center` with an explicit `None` fillchar now raise CPython's TypeError instead of silently padding with spaces. This is a fixed silent difference; `test_ail_fuzz51.py` keeps the case. |
