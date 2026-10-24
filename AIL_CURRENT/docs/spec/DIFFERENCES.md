# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre172-10250444-1 | integers / unary constants | A statically known unary integer expression outside int64 (`-MIN` on a module constant, or `-(-9223372036854775808)`) used to compile on the default build and trap at run time with `integer overflow`; CPython prints a bignum. Both builds now refuse it by name (`int64 constant expression out of range: ...`); variables that only reach the operation at run time keep the fixed-width trap. Covered by `test_ail_pre172.py`. | fixed |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
# Differences from CPython 3.12

Rows are behaviours where this compiler deliberately differs from CPython, or
behaviours it refuses by name. New ids from worker branches use the placeholder
form `C?-<branch>-N`.

| id | area | difference |
| --- | --- | --- |
| C?-job-fuzz51-10231205-1 | bytes/bytearray padding | `ljust`, `rjust` and `center` with an explicit `None` fillchar now raise CPython's TypeError instead of silently padding with spaces. This is a fixed silent difference; `test_ail_fuzz51.py` keeps the case. |
| C?-job-fuzz37-10230931-1 | ordering comparisons | A TypeError from `<`, `<=`, `>`, `>=` on built-in values that cannot be ordered now names the operator that was written, as CPython does, instead of always naming `<`. This is not a deliberate difference; the row records the fixed behaviour and the fuzz37 regression test. |
