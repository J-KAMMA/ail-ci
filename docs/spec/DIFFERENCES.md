# Differences from CPython

| id | status | summary |
| --- | --- | --- |
| C?-job-fuzz13-10220829-1 | fixed | Float `%` and `divmod` returned `0.0` for an exact multiple where CPython takes the divisor's sign (`5.0 % -5.0` is `-0.0`). The boxed runtime and the unboxed float lowering now use `copysign(0.0, divisor)` for a zero remainder. |
| C?-job-fuzz13-10220829-2 | fixed | `sum(xs, "")` concatenated strings instead of raising CPython's `TypeError`, and a tuple start made the typed pass print a truncated fixed-shape tuple (`sum([(1,), (2,)], ())` printed `()`). A str start now raises the CPython `TypeError`; a tuple start leaves the result type open so the generic tuple value is printed. |
| C?-job-fuzz13-10220829-3 | fixed | Two-argument `min()`/`max()` of an int and a float on the default build rounded the int to double, so values above 2**53 compared equal and the wrong operand (or a float instead of the int) was returned. That shape now uses the general path's exact boxed comparison and keeps the selected operand's type. |
