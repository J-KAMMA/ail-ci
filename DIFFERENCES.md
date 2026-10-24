# DIFFERENCES

Deliberate differences from CPython and open silent differences found by differential jobs.

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre165-10250411-1 | nested def forward call | A direct call of a nested `def` before its own `def` statement printed the function's result on both builds; CPython reads an unbound local and raises `UnboundLocalError: cannot access local variable 'f' where it is not associated with a value`. The general path now checks a def-time binding flag before the call; a name also bound by a parameter, assignment, loop target or `except ... as` reads the frame slot, and every such rebinding clears the flag. The typed path refuses the shape by name and the default build falls back. | fixed |
| C?-job-pre166-10250412-1 | `next()` / generator expressions | A generator expression saved in a name, an argument, a list item, a dict value or an attribute (or returned in a list) was a materialised list with no cursor, so `next()` on it hit `AIL internal error: iterator: unknown kind`; `next()` of any other non-iterator (for example a plain list) hit the same internal error instead of CPython's `TypeError`. The list now keeps one shared cursor for `next()`, iteration and `in` (which consumes up to and including a match, or to the end), and a non-iterator raises `TypeError: '<type>' object is not an iterator`. | fixed |
| C?-job-pre173-10250445-1 | bytes/bytearray search bounds | Non-index start/end bounds of `find`, `rfind`, `count`, `index`, `rindex`, `startswith` and `endswith` were read as an index (a str bound raised `'<' not supported between instances of 'str' and 'int'`); they now follow CPython's slice-index conversion, including `__index__` and its non-int TypeError. | fixed; `test_ail_pre173.py` |
| C?-job-pre90-10242040-1 | `chr()` / 16-bit strings | The general path's v2 runtime could not store a surrogate or non-BMP code point: `chr(0x10000)` built and then died with an internal error at run time, although the same text as a literal was already refused by name at compile time. Constant `chr()` calls in those ranges are now refused by name at compile time on both builds, and the runtime store follows the host unit width so a 32-bit build stores the value instead of truncating it. | refused |
| C?-job-pre90-10242040-2 | `chr()` / 16-bit strings | A non-BMP code point that reaches `chr()` only at run time still dies with the 16-bit runtime's internal error; compile-time constants are refused by name by row 1. | open |
| C?-job-pre93-10242042-1 | bare annotations on attribute/subscript targets | A function-local bare annotation (`box().x: int`, `xs[i()]: int`) dropped the target's subexpressions, so the calls did not run; CPython evaluates them without reading the attribute or performing the final subscript, and never evaluates the annotation. The attribute target used to become `pass`. Module-scope targets are evaluated too; annotations there remain hints. Target parts now go through the surface rewriter (imported names such as `from math import floor` work), and a `Slice` inside a tuple target is flattened into its lower/upper/step parts. | fixed; `test_ail_pre93.py` |
| C?-job-fuzz45-10231201-1 | integer/float `//`, `%`, `divmod` | The general path computed float floor division as `floor(a / b)` and float modulo from `fmod` with only a sign fix. `1.0 // 0.1` printed 10.0 (CPython 9.0), `-0.0 % 2.0` printed -0.0 (CPython 0.0), `-5.0 // inf` printed -0.0 (CPython -1.0), `inf // 2.0` printed inf (CPython nan). Fixed on both general emitters with one CPython float_divmod helper. | fixed |
| C?-job-pre171-10250443-1 | mixed mode / indirect call | A negative shift (`<<`/`>>`, also augmented) in a helper called from a lambda, a list entry or a callback escaped the caller's boxed `try` on the default build because `pymix` followed only direct calls by name; the helper's typed `ValueError` bypassed the handler. Trap-capable candidates invoked indirectly are now rejected to the general path, and the typed shift guards name CPython's `negative shift count`. | fixed; `test_ail_pre171.py` |
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

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre177-10250448-1 | int64 / constant subscript | A constant subscript index (or a constant `**`) that leaves int64 is refused by name (`int64 index out of range` / `int64 constant out of range`, exit 2) instead of stopping with `integer overflow`; CPython raises `IndexError: cannot fit 'int' into an index-sized integer` for `xs[10**20]`. In-range constant index expressions still match CPython. | refused by name; `test_ail_pre177.py` |
