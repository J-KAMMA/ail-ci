# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-rbpre23-10242019-1 | bytes / str codecs | tab- and colon-normalized encoding names such as `utf\t8` and `iso-8859-1:1987` raised LookupError (literal names were also refused at compile time) instead of naming CPython's UTF-8 / Latin-1 | fixed: names are normalized like `encodings.normalize_encoding`; the runtime and both compile-time checks use the same alias table |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
# Differences from CPython 3.12

Rows are behaviours where this compiler deliberately differs from CPython, or
behaviours it refuses by name. New ids from worker branches use the placeholder
form `C?-<branch>-N`.

| id | area | difference |
| --- | --- | --- |
| C?-job-pre108-10242222-1 | integers | A statically known integer constant expression outside int64 (for example `9223372036854775807 * 2`) used to compile and then stop at run time with `integer overflow`; CPython prints a bignum. The front end now evaluates literal and module-constant expressions and refuses the construct by name (`int64 constant expression out of range: ...`) on both builds. Values that only reach the operation at run time keep the fixed-width trap. |
| C?-job-pre134-10250029-1 | `del` of a class name | `class C: pass; del C` made both builds fail with the compiler's own `KeyError: 'C'`; the name lives in a dedicated class slot and the same refusal covers a module-scope rebinding, so the deletion is now refused by name at compile time (`del on the class name C`). `test_ail_pre134.py` keeps the case. |
| C?-job-fuzz51-10231205-1 | bytes/bytearray padding | `ljust`, `rjust` and `center` with an explicit `None` fillchar now raise CPython's TypeError instead of silently padding with spaces. This is a fixed silent difference; `test_ail_fuzz51.py` keeps the case. |
| C?-job-fuzz37-10230931-1 | ordering comparisons | A TypeError from `<`, `<=`, `>`, `>=` on built-in values that cannot be ordered now names the operator that was written, as CPython does, instead of always naming `<`. This is not a deliberate difference; the row records the fixed behaviour and the fuzz37 regression test. |
