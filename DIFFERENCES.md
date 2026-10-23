# DIFFERENCES

| id | status | behaviour |
|---|---|---|
| C?-job-fuzz42-10231159-1 | fixed | General-path `abs()` returned a bool argument unchanged (`abs(False)` printed `False`, `abs(True)` printed `True`); CPython returns the ints `0` and `1`. The plain call and the builtin-as-`key=`/`map()` wrapper now use `ail_bi_abs`. |
