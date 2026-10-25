# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre182-10251541-1 | bytes/bytearray padding fillchar | `ljust`, `rjust` and `center` converted the fillchar with the generic bytes helper before checking its type, so a str, int, bool, list or user-class fillchar raised `a bytes-like object is required, not '<type>'` instead of CPython's `<method>() argument 2 must be a byte string of length 1, not <type>`. The type check now runs before the conversion, so a non-bytes fillchar names the method and its type, while a bytes/bytearray fillchar of the wrong length keeps naming bytes/bytearray. Explicit `None` still says `not None` from the fuzz51 fix. Added `test_ail_pre182.py`. | fixed |
| C?-job-rbpre23-10242019-1 | bytes / str codecs | tab- and colon-normalized encoding names such as `utf\t8` and `iso-8859-1:1987` raised LookupError (literal names were also refused at compile time) instead of naming CPython's UTF-8 / Latin-1 | fixed: names are normalized like `encodings.normalize_encoding`; the runtime and both compile-time checks use the same alias table |
| C?-job-pre173-10250445-1 | bytes/bytearray search bounds | Non-index start/end bounds of `find`, `rfind`, `count`, `index`, `rindex`, `startswith` and `endswith` were read as an index (a str bound raised `'<' not supported between instances of 'str' and 'int'`); they now follow CPython's slice-index conversion, including `__index__` and its non-int TypeError. | fixed; `test_ail_pre173.py` |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
# Differences from CPython 3.12

Rows are behaviours where this compiler deliberately differs from CPython, or
behaviours it refuses by name. New ids from worker branches use the placeholder
form `C?-<branch>-N`.

| id | area | difference |
| --- | --- | --- |
| C?-job-pre134-10250029-1 | `del` of a class name | `class C: pass; del C` made both builds fail with the compiler's own `KeyError: 'C'`; the name lives in a dedicated class slot and the same refusal covers a module-scope rebinding, so the deletion is now refused by name at compile time (`del on the class name C`). `test_ail_pre134.py` keeps the case. |
| C?-job-fuzz51-10231205-1 | bytes/bytearray padding | `ljust`, `rjust` and `center` with an explicit `None` fillchar now raise CPython's TypeError instead of silently padding with spaces. This is a fixed silent difference; `test_ail_fuzz51.py` keeps the case. |
| C?-job-fuzz37-10230931-1 | ordering comparisons | A TypeError from `<`, `<=`, `>`, `>=` on built-in values that cannot be ordered now names the operator that was written, as CPython does, instead of always naming `<`. This is not a deliberate difference; the row records the fixed behaviour and the fuzz37 regression test. |
