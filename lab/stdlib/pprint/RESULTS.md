# `pprint` coverage results

Build command: `python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/pprint/<program>.py --syntax python -o <exe>`
(default mode: typed path first, general path when the typed path refuses).  Each built program was run
next to `python3 <program>.py`; stdout and exit status match CPython 3.12 in all cases.

| Program | Result | First typed-path refusal (default build falls back to the general path) |
| --- | --- | --- |
| p01_nested.py | general | ``{'user': {'name': 'Ada', 'id': 42}, '...` mixes bools and numbers; Python keeps each value's own type and a number would print as 1 / 0.` |
| p02_width_indent.py | general | `import of 'pprint' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |
| p03_depth.py | general | ``{'level1': {'level2': {'level3': [1, ...` mixes bools and numbers; Python keeps each value's own type and a number would print as 1 / 0.` |
| p04_compact.py | general | `import of 'pprint' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |
| p05_sort_dicts.py | general | `import of 'pprint' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |
| p06_prettyprinter.py | general | `import of 'pprint' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |
| p07_stream.py | general | `import of 'pprint' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |
| p08_saferepr.py | general | ``[None, True, 3, -12, 2.5, 'text', [1,...` mixes bools and numbers; Python keeps each value's own type and a number would print as 1 / 0.` |
| p09_underscore.py | general | `import of 'pprint' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |
| p10_strings.py | general | `import of 'pprint' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |
| p11_errors.py | general | `import of 'pprint' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |
| p12_edge_cases.py | general | `import of 'pprint' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).` |

Every refusal above continues with the same hint:

```
  write instead: drop the import and write what you need by hand with plain lists, dicts and loops
```

(or, for the three "mixes bools and numbers" refusals, `write instead: make every operand a bool (or int(...) every operand)`).

## What was added

`pprint` is lowered on the general path (`python/pkg-v12/genlib.py`, `prelude_genlib.py`), like `json`,
`statistics`, `datetime` and `itertools`: `pprint`, `pformat`, `pp`, `saferepr`, `isreadable`,
`isrecursive` and `PrettyPrinter` are renamed to Python-source pieces that reproduce CPython 3.12's
`pprint.py` for dict / list / tuple / set / frozenset / str / bytes / bytearray / int / float / bool /
None.  Supported keyword arguments: `stream`, `indent`, `width`, `depth`, `compact`, `sort_dicts`,
`underscore_numbers`.  The signatures match CPython's: `compact` and the keywords after it are
keyword-only, so an extra positional argument is refused by name instead of silently accepted.  Recursive
containers use the same active-object context as CPython and print `<Recursion on ... with id=N>` instead
of recursing until the process crashes; the number is the compiled process's own address, so it cannot
equal the address CPython printed.  Long `bytes` / `bytearray` values wrap in four-byte chunks like
CPython.  The programs also exercise empty containers, singleton tuples, depth limits, compact wrapping,
insertion order, `io.StringIO` streams, long `bytes` / `bytearray` wrapping, and the `ValueError`s from
`indent < 0`, `depth <= 0` and `width == 0`.

All 12 programs build and match; the `test_ail_std_pprint` test checks all 12 with both the default
build and `AIL_IR=1`, plus a recursive-container case whose CPython/compiled `id=` numbers are
normalised by the test.

## Follow-up (needs a larger feature, not fixed here)

* The typed path still refuses `import pprint`:

  ```
  not in the subset: import of 'pprint' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).
  ```

* The prelude reproduces pprint for the built-in containers above.  It does not implement CPython's
  dispatch for dataclasses, `OrderedDict`, `Counter`, `defaultdict`, `ChainMap`, `deque`, `UserDict`,
  `UserList`, `UserString`, `types.MappingProxyType` or `types.SimpleNamespace`.  A program using those
  would need the extra-type dispatch that the general path does not provide.  Recursive containers and
  long `bytes` / `bytearray` are handled; the only difference in the `<Recursion ... id=N>` text is the
  address itself, which is process-specific in CPython too.
