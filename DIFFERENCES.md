# DIFFERENCES

Deliberate differences from CPython and open silent differences found by differential jobs.

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre26-10240859-1 | exception arguments | On the typed path `e.args[i]` reads as text, so `repr(e.args[i])` quoted numeric, bool and None arguments (`'3.0'` instead of `3.0`). The handler rewrite now formats the stored argument for `repr`, `!r` and `%r`; both builds match CPython. | fixed |
| C?-job-fuzz45-10231201-1 | integer/float `//`, `%`, `divmod` | The general path computed float floor division as `floor(a / b)` and float modulo from `fmod` with only a sign fix. `1.0 // 0.1` printed 10.0 (CPython 9.0), `-0.0 % 2.0` printed -0.0 (CPython 0.0), `-5.0 // inf` printed -0.0 (CPython -1.0), `inf // 2.0` printed inf (CPython nan). Fixed on both general emitters with one CPython float_divmod helper. | fixed |
| id | area | CPython | AIL | disposition |
| --- | --- | --- | --- | --- |
| C?-job-fuzz39-10230820-1 | `is` / `is not` with a tuple constant | merges equal tuple constants of a code object (`a = (); b = (); a is b` is True; `()` is a singleton) | each tuple display is an object of its own | refused by name; `test_ail_fuzz39.py` |
