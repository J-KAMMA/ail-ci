# Differences from CPython

This CI mirror does not carry the development copy of docs/spec/DIFFERENCES.md; the rows for this
job use the placeholder ids the job asks for.

| id | area | difference |
| --- | --- | --- |
| C?-job-fuzz19-10220951-1 | general path, rich comparison | before this job, `<=`, `>`, `>=` on instances used the `<` tables instead of `__le__`/`__gt__`/`__ge__`; fixed in dunderrt.py / safetyrt.py |
| C?-job-fuzz19-10220951-2 | general path, generator expression | before this job, `any()`/`all()` evaluated every element of a generator expression instead of stopping at the first decisive one; fixed in pyboxed2.py |

Other observed differences left in place (not fixed):

* A chained comparison whose `__eq__`/`__lt__` returns a non-bool (for example `0` or `-1`) returns
  a bool in AIL where CPython returns that operand value (`0 == 0 == 0` with a custom `__eq__`).
* `repr()` of a value statically inferred as a list but holding an int (a heterogeneous list whose
  first element is a list) takes the list-repr helper and raises "'int' object is not iterable".
* Chained comparisons of integer expressions that overflow int64 stop with "integer overflow";
  CPython has unbounded ints.
* Some for-else / while-else shapes with `continue` out of a `try/finally` are refused by name.
