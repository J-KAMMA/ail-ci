# Differences from CPython

New rows found by the fuzz jobs use the placeholder id `C?-<branch>-N`.

| id | area | difference |
|----|------|------------|
| C?-job-fuzz21-10230420-1 | integers | An integer literal/expression beyond 64 bits (for example `10**50`) traps with `integer overflow` on both builds; CPython prints the value. This is outside unpacking, which the same probe otherwise matches. |
