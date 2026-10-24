# DIFFERENCES

Deliberate differences from CPython and open silent differences found by differential jobs.

| id | area | difference | status |
| --- | --- | --- | --- |
| C168 | `str.find`/`rfind`/`count`/`startswith`/`endswith`/`index`/`rindex` with a `None` start or end | The general path treated a supplied `None` bound as a present bound with index 0, i.e. an empty window: `"hello".find("l", None, None)` gave -1 where CPython gives 2, and the same held for every method in the family and for a `None` that arrived through a variable, a function argument, a list item, a dict value or an attribute. The emitter (`AIL_CURRENT/python/pkg-v12/pyboxed2.py`) now tests each supplied bound's tag and passes `has_lo = 0` / `has_hi = 0` for a `None`, matching CPython and the typed path. | fixed |
| C?-job-fuzz45-10231201-1 | integer/float `//`, `%`, `divmod` | The general path computed float floor division as `floor(a / b)` and float modulo from `fmod` with only a sign fix. `1.0 // 0.1` printed 10.0 (CPython 9.0), `-0.0 % 2.0` printed -0.0 (CPython 0.0), `-5.0 // inf` printed -0.0 (CPython -1.0), `inf // 2.0` printed inf (CPython nan). Fixed on both general emitters with one CPython float_divmod helper. | fixed |
| id | area | CPython | AIL | disposition |
| --- | --- | --- | --- | --- |
| C?-job-fuzz39-10230820-1 | `is` / `is not` with a tuple constant | merges equal tuple constants of a code object (`a = (); b = (); a is b` is True; `()` is a singleton) | each tuple display is an object of its own | refused by name; `test_ail_fuzz39.py` |
