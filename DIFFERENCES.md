# Known differences from CPython

| id | area | status | detail |
|----|------|--------|--------|
| C?-job-fuzz18-10220949-1 | `math.fsum` | fixed | Non-finite inputs and intermediate overflow now raise CPython's `ValueError`/`OverflowError`; int elements are converted to float. |
| C?-job-fuzz18-10220949-2 | float `//`, `%`, `divmod` | fixed | Signed zero, `inf // 2`, `3.0 // -inf` and NaN operands now use CPython's `float_divmod` rules in both runtime paths. |
| C?-job-fuzz18-10220949-3 | math helpers, wrong types | fixed | `math.copysign/hypot/atan2/fmod/pow/sin/cos/fabs/isnan/sqrt/...` on a str/None now raise `TypeError must be real number, not ...` instead of printing garbage. |
| C?-job-fuzz18-10220949-4 | `math.floor/ceil/trunc` and `int()` of large floats | open | A finite float above int64 (e.g. `9.3e18`, `1e300`) stops the program with `integer overflow`; CPython returns a big int. AIL ints are int64, so this is a size limit, not a wrong value. |
| C?-job-fuzz18-10220949-5 | zero-division wording | open | `1 / 0.0` says `division by zero` (CPython: `float division by zero`); `1 % 0` says `integer division or modulo by zero` (CPython: `integer modulo by zero`). The exception type is right. |
| C?-job-fuzz18-10220949-6 | `math.isclose` wrong types | open | `math.isclose('a', 'b')` raises `ValueError could not convert string to float`; CPython raises `TypeError must be real number, not str`. Values for valid numeric arguments match. |
| C?-job-fuzz18-10220949-7 | `sorted()` with NaN | open | A list mixing NaN, infinities and finite floats can come out in a different order than CPython (CPython's result itself depends on the comparison sequence). |
| C?-job-fuzz18-10220949-8 | `math.fsum` with a generator | open | `math.fsum(gen())` stops with `TypeError object of type 'instance' has no len()`; CPython accepts any iterable. Lists and tuples are built. |
