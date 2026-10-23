# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
| C?-job-pre21-10240310-1 | float `%` | the boxed runtime kept `fmod`'s zero sign (the dividend's) instead of the divisor's: `0.0 % -3.0` printed `0.0` and `-0.0 % 3.0` printed `-0.0`; nonzero remainders were already corrected | fixed: a zero remainder now takes the divisor's sign on both paths |
