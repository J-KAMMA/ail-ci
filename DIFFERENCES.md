# DIFFERENCES

Deliberate differences from CPython and open silent differences found by differential jobs.

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre168-10250413-1 | itertools | `list(itertools.permutations(...))`, `list(itertools.combinations(...))` and `list(itertools.product(a, b, ...))` (also `return list(...)`) over a tuple-yielding stream emitted `ail_list_push` with an `ail_list` (bad C) on the typed path when the pool elements were ints or floats; CPython builds a list of tuples. The typed lowering now refuses this construct by name, so the default build falls back to the general path, which matches CPython. | refused by name; `test_ail_pre168.py` |
| C?-job-fuzz45-10231201-1 | integer/float `//`, `%`, `divmod` | The general path computed float floor division as `floor(a / b)` and float modulo from `fmod` with only a sign fix. `1.0 // 0.1` printed 10.0 (CPython 9.0), `-0.0 % 2.0` printed -0.0 (CPython 0.0), `-5.0 // inf` printed -0.0 (CPython -1.0), `inf // 2.0` printed inf (CPython nan). Fixed on both general emitters with one CPython float_divmod helper. | fixed |
| id | area | CPython | AIL | disposition |
| --- | --- | --- | --- | --- |
| C?-job-fuzz39-10230820-1 | `is` / `is not` with a tuple constant | merges equal tuple constants of a code object (`a = (); b = (); a is b` is True; `()` is a singleton) | each tuple display is an object of its own | refused by name; `test_ail_fuzz39.py` |
| C?-job-fuzz43-10231200-1 | str search: startswith/endswith tuple prefixes | A tuple member that was not a str raised the right TypeError but printed `instance` instead of its class name, so `"abc".startswith((b"a",))` printed `tuple for startswith must only contain str, not instance` where CPython prints `not bytes`; user-class members were also flattened to `instance`. The checks now resolve the member object's class name on both builds. | fixed |
Rows added by job-fuzz8-10220554 use the placeholder id form requested for this branch.

| id | status | area | description |
|---|---|---|---|
| C?-job-fuzz8-10220554-1 | open | itertools | `permutations` / `combinations` / `combinations_with_replacement` with a negative `r` return `[]` on the general path; CPython raises `ValueError: r must be non-negative`. |
| C?-job-fuzz8-10220554-2 | open | enumerate | `enumerate(xs, start)` with `None`, a float, a str or a list is accepted on the general path (None becomes 0, the others are read as a pointer-sized value) instead of raising `TypeError: '<type>' object cannot be interpreted as an integer`. |
| C?-job-fuzz8-10220554-3 | open | reversed | `reversed` of a dict, a dict view or a bytearray raises `TypeError: '<type>' object is not reversible` at run time; CPython 3.12 reverses all of them. |
| C?-job-fuzz8-10220554-4 | open | groupby | `print`/`repr` of an unread `groupby` grouper shows `<object>`; CPython shows `<itertools._grouper object at 0x...>` (the address cannot match byte for byte anyway). |
| C?-job-fuzz8-10220554-5 | open | nesting | On the general path `map` / `filter` / `zip` / `enumerate` over a library iterator (for example `map(f, itertools.accumulate(...))`) dies with `AIL internal error: iterator: unknown kind`; the core `AIL_IT_MAP`/`FILTER`/`ZIP`/`ENUMERATE` cases call the core dispatcher, not `ail_it_next`, for their source. |
| C?-job-fuzz8-10220554-6 | refused | zip_longest | More than two iterables (with or without `fillvalue=`) are refused by name by the default lowering, although CPython accepts them; `zip_longest(*[[1, 2], [3]])` is refused too. |
| C?-job-fuzz8-10220554-7 | refused | starmap | A callable that is not exactly two arguments (a 1- or 3-argument def, `pow` with triples) is refused by name; CPython calls it with every tuple element. |
| C?-job-fuzz8-10220554-8 | refused | zip | `zip(..., strict=True)` is refused by name when there are more than two iterables. |
| C?-job-fuzz8-10221632-1 | refused | accumulate | On the typed path `itertools.accumulate(xs, initial=v)` is refused by name when `v` has a different type from the elements (for example one-argument `round()` is an `int` over a `list[float]`); the default build falls back to the general path, which matches CPython. |
| C?-job-fuzz8-10221632-2 | open | groupby | With mutable elements (for example `list[list[int]]`) the typed path cannot lower the key look-ahead yet: `--strict` refuses it (`'_ilN_gc' is read before it is assigned`), so the default build falls back to the general path, which matches CPython. Keys over scalar/str element lists stay on the typed path and are called once per element. |
# Differences from CPython (record)

| ID | Area | Status | Description |
| --- | --- | --- | --- |
| C?-job-fuzz65-10231438-1 | heapq / list repr | fixed | After a caught `heappush` TypeError on a `list[int]` (CPython appends before comparing), the annotation-specialized list repr printed a string element as `x` instead of `'x'` when a tuple comparison had generated that helper. Scalar elements now use the runtime value's `repr`. |
Known differences from CPython. New rows use `C?-<branch>-N` until a maintainer assigns an id.

| id | area | difference | status |
|----|------|------------|--------|
| C?-job-fuzz89-10231611-1 | bytes.split / bytes.rsplit | With a `None` separator and a reached `maxsplit`, the unsplit remainder lost its outer whitespace (`b" a ".split(None, 0)` gave `[b"a"]`; CPython gives `[b"a "]`, and the mirror case in `rsplit`). | fixed in safetyrt.py |
