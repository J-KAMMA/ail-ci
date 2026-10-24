# DIFFERENCES

Deliberate differences from CPython and open silent differences found by differential jobs.

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-cov7-10240917-1 | compiler crashes | The general path built a `functools.partial()` closure from `Lambda` nodes without line numbers, so `g17_004` / `g17_024` ended in `AttributeError: 'Lambda' object has no attribute 'lineno'`; the typed dispatcher chose a stubbed abstract base method as its representative and `g13_036` ended in `KeyError: 'Visitor__visit_directory'`. Both now compile and match CPython; `test_ail_silent6.py` and `test_ail_typed_inherit.py` cover them. | fixed |
| C?-job-fuzz45-10231201-1 | integer/float `//`, `%`, `divmod` | The general path computed float floor division as `floor(a / b)` and float modulo from `fmod` with only a sign fix. `1.0 // 0.1` printed 10.0 (CPython 9.0), `-0.0 % 2.0` printed -0.0 (CPython 0.0), `-5.0 // inf` printed -0.0 (CPython -1.0), `inf // 2.0` printed inf (CPython nan). Fixed on both general emitters with one CPython float_divmod helper. | fixed |
| id | area | CPython | AIL | disposition |
| --- | --- | --- | --- | --- |
| C?-job-fuzz39-10230820-1 | `is` / `is not` with a tuple constant | merges equal tuple constants of a code object (`a = (); b = (); a is b` is True; `()` is a singleton) | each tuple display is an object of its own | refused by name; `test_ail_fuzz39.py` |
| C?-job-fuzz43-10231200-1 | str search: startswith/endswith tuple prefixes | A tuple member that was not a str raised the right TypeError but printed `instance` instead of its class name, so `"abc".startswith((b"a",))` printed `tuple for startswith must only contain str, not instance` where CPython prints `not bytes`; user-class members were also flattened to `instance`. The checks now resolve the member object's class name on both builds. | fixed |
