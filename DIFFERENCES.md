# Differences from CPython

This CI mirror does not carry the development copy of docs/spec/DIFFERENCES.md; the rows for this
job use the placeholder ids the job asks for.

| id | area | difference |
| --- | --- | --- |
| C?-job-fuzz19-10220951-1 | general path, rich comparison | before this job, `<=`, `>`, `>=` on instances used the `<` tables instead of `__le__`/`__gt__`/`__ge__`; fixed in dunderrt.py / safetyrt.py. The runtime path (a list item, dict value, attribute or argument whose class is not statically known) now returns the method's value, not a coerced bool, and chains do the same. |
| C?-job-fuzz19-10220951-2 | general path, generator expression | before this job, `any()`/`all()` evaluated every element of a generator expression instead of stopping at the first decisive one; fixed in pyboxed2.py. When the loop stops early it closes the abandoned generator source(s), outermost first, so their finally blocks run. |
| C?-job-fuzz19-10220951-3 | general path, generators | before this job, `g.close()` finished a suspended generator without running its finally blocks; fixed in safetyrt.py. A never-started or already-finished generator is unchanged, and an exception raised by a finally during close propagates as CPython's does. |

Other observed differences left in place (not fixed):

* `repr()` of a value statically inferred as a list but holding an int (a heterogeneous list whose
  first element is a list) takes the list-repr helper and raises "'int' object is not iterable".
* Chained comparisons of integer expressions that overflow int64 stop with "integer overflow";
  CPython has unbounded ints.
* Some for-else / while-else shapes with `continue` out of a `try/finally` are refused by name.
