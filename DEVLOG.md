# DEVLOG

## 2026-10-22 -- job-fuzz19-10220951 review fixes

The review found two regressions in the fuzz19 commit, both fixed and covered by tests:

* The lazy `any()`/`all()` fused loop stopped without closing the temporary generator expression's
  source, so a generator's `finally` never ran. The loop now closes abandoned sources (outermost
  first, matching CPython's deallocation order); `g.close()` itself now resumes a suspended generator
  with a private completion status so its `finally` blocks run too.
* Runtime-dispatched `<`, `<=`, `>` and `>=` boxed the method's result to bool. They now return the
  method's value, as the statically dispatched path does, for list items, dict values, attributes,
  arguments and chains.

Also, the ordering helpers and enum entries are only emitted for a program that actually contains an
ordering comparison, so a class program that never compares instances gets the same C as before.

## 2026-10-22 -- job-fuzz19-10220951 (control flow)

Fuzz round 19 compared 80 small control-flow programs (for/while else, break/continue, nested
loops, walrus in conditions and comprehensions, match patterns, chained comparisons, and/or)
against CPython 3.12 on both builds. Two silent causes were fixed:

* The general path's runtime only dispatched `__lt__`/`__gt__`; `<=`, `>`, `>=` on instances fell
  back to `<` and printed the wrong method calls. Rich comparison now calls the left operator and
  then the right operand's reflected operator, including `NotImplemented`, chains, and values that
  arrive through locals, tuple assignments, arguments, list items, attributes and dict values.
* `any()` / `all()` over a generator expression were not lazy: the fused loop evaluated every
  element before reading the answer, so later side effects and exceptions happened. The loop now
  stops at the first decisive element at every nesting level.

The remaining differences found by this round are listed in DIFFERENCES.md.
