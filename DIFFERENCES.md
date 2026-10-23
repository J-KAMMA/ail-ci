# DIFFERENCES

Deliberate differences from CPython and open silent differences found by differential jobs.

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-fuzz84-10231555-1 | text processing: str.split/rsplit/splitlines argument binding | A keyword CPython finds already filled by a positional was silently ignored, so `"a,b".split(",", sep="-")` printed `['a', 'b']`, `"a,b,c".split(",", 1, maxsplit=2)` and `"a,b".rsplit(",", sep="-")` printed normal results, and `"a\nb".splitlines(True, keepends=False)` used only `True`; CPython raises `TypeError` for each. The compiler now refuses all four by name. | fixed |
