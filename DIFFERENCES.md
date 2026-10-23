# Differences from CPython 3.12

| id | area | difference |
| --- | --- | --- |
| C?-job-fuzz63-10231421-1 | float `%` | A zero remainder kept the sign `fmod()` returned (`-0.0 % 1.0` printed `-0.0`, `0.0 % -1.0` printed `0.0`). CPython returns `copysign(0.0, divisor)`; fixed on the general, unified and boxed paths. Covered by `test_ail_fuzz63.py`. |
