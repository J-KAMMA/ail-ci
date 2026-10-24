# DIFFERENCES

Deliberate differences from CPython and open silent differences found by differential jobs.

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre33-10240909-1 | integer power `**` beyond int64 | CPython's int is unbounded, so `10 ** 40` is an exact integer (and can be printed, put in a tuple, etc.). AIL's int is int64 (SEMANTICS section 1), so a constant integer power whose exact result does not fit is refused at compile time by name instead of wrapping or stopping at run time. Powers that fit, including `2 ** 62`, `(-2) ** 63` (INT64_MIN) and bases -1/0/1 under a huge exponent, still compile and match CPython. | refused by name; `test_ail_pre33.py` |
| C?-job-fuzz45-10231201-1 | integer/float `//`, `%`, `divmod` | The general path computed float floor division as `floor(a / b)` and float modulo from `fmod` with only a sign fix. `1.0 // 0.1` printed 10.0 (CPython 9.0), `-0.0 % 2.0` printed -0.0 (CPython 0.0), `-5.0 // inf` printed -0.0 (CPython -1.0), `inf // 2.0` printed inf (CPython nan). Fixed on both general emitters with one CPython float_divmod helper. | fixed |
| id | area | CPython | AIL | disposition |
| --- | --- | --- | --- | --- |
| C?-job-fuzz39-10230820-1 | `is` / `is not` with a tuple constant | merges equal tuple constants of a code object (`a = (); b = (); a is b` is True; `()` is a singleton) | each tuple display is an object of its own | refused by name; `test_ail_fuzz39.py` |
