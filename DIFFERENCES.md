# DIFFERENCES

Deliberate differences from CPython and open silent differences found by differential jobs.

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-fuzz45-10231201-1 | integer/float `//`, `%`, `divmod` | The general path computed float floor division as `floor(a / b)` and float modulo from `fmod` with only a sign fix. `1.0 // 0.1` printed 10.0 (CPython 9.0), `-0.0 % 2.0` printed -0.0 (CPython 0.0), `-5.0 // inf` printed -0.0 (CPython -1.0), `inf // 2.0` printed inf (CPython nan). Fixed on both general emitters with one CPython float_divmod helper. | fixed |
| id | area | CPython | AIL | disposition |
| --- | --- | --- | --- | --- |
| C?-job-fuzz39-10230820-1 | `is` / `is not` with a tuple constant | merges equal tuple constants of a code object (`a = (); b = (); a is b` is True; `()` is a singleton) | each tuple display is an object of its own | refused by name; `test_ail_fuzz39.py` |
| C?-job-fuzz43-10231200-1 | str search: startswith/endswith tuple prefixes | A tuple member that was not a str raised the right TypeError but printed `instance` instead of its class name, so `"abc".startswith((b"a",))` printed `tuple for startswith must only contain str, not instance` where CPython prints `not bytes`; user-class members were also flattened to `instance`. The checks now resolve the member object's class name on both builds. | fixed |
| C?-job-pre34-10240952-1 | `%` formatting, literal `%d` | `"%d%%" % 60.0654` prints `60%`; `%d` truncates a float and a non-number raises `%d format: a real number is required, not str` | the general path sent a literal `%d` operand to `ail_obj_format` (int/bool only), so a float percentage raised `TypeError: unsupported format string passed to non-int` and a non-number got that same wrong message. `%i`/`%u` and computed templates already matched through `safetyrt.ail2f_percent`; literal `%d` now keeps the direct formatter for int/bool and sends other values to it. Out-of-int64 finite floats stay the documented int64 limit. | fixed on both builds; `test_ail_pre34.py` |
