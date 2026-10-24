# DIFFERENCES

Deliberate differences from CPython and open silent differences found by differential jobs.

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-fuzz45-10231201-1 | integer/float `//`, `%`, `divmod` | The general path computed float floor division as `floor(a / b)` and float modulo from `fmod` with only a sign fix. `1.0 // 0.1` printed 10.0 (CPython 9.0), `-0.0 % 2.0` printed -0.0 (CPython 0.0), `-5.0 // inf` printed -0.0 (CPython -1.0), `inf // 2.0` printed inf (CPython nan). Fixed on both general emitters with one CPython float_divmod helper. | fixed |
| C?-job-pre43-10241006-1 | dict construction, update and copy | `dict(d)`, `d.copy()` and `d.update(other_dict)` called a user `__eq__` a different number of times than CPython when the source key table could be cloned or had just been preallocated; a clean source was always cloned and a dirty one always reinserted. Both builds now track CPython 3.12's `dk_nentries`, trailing dummies and table capacity: `dict(d)`/empty-target `update` clones only under CPython's capacity condition, otherwise preallocates `estimate_log2_keysize(used_a+used_b)` and inserts stored hashes; `copy` uses the fast clone only when at most one third of the entry slots are dead; `popitem` drops trailing dummies and `clear` resets the key table. Values and order were already the same, and stored keys still never re-run `__hash__`. | fixed 2026-10-24 |
| id | area | CPython | AIL | disposition |
| --- | --- | --- | --- | --- |
| C?-job-fuzz39-10230820-1 | `is` / `is not` with a tuple constant | merges equal tuple constants of a code object (`a = (); b = (); a is b` is True; `()` is a singleton) | each tuple display is an object of its own | refused by name; `test_ail_fuzz39.py` |
| C?-job-fuzz43-10231200-1 | str search: startswith/endswith tuple prefixes | A tuple member that was not a str raised the right TypeError but printed `instance` instead of its class name, so `"abc".startswith((b"a",))` printed `tuple for startswith must only contain str, not instance` where CPython prints `not bytes`; user-class members were also flattened to `instance`. The checks now resolve the member object's class name on both builds. | fixed |
