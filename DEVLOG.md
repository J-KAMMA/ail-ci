# DEVLOG

## 2026-10-21 -- `re.sub` / `re.subn` with a function as the replacement (job-resub2)

`re.sub(P, f, s)` crashed at run time (`TypeError: argument of type 'function' is not iterable`) unless `f`
was spelled as a lambda literal or as a def name never rebound: the surface decided between the callable
helper (`_ail_re_subN(s, fn, count)`, which calls `fn` with each Match) and the string helper
(`_ail_re_sublit`, a replacement template) by looking at the *syntax* of the argument.

`ail_syntax._Surface.collect_repl` now resolves the names whose every binding is a function value and
`re_repl_kind` answers for an expression: a lambda, a def, a name that holds one (`f = up`, `g = f`,
`h = i = up`, `f = lambda m: ...`), a dict or list of functions indexed at run time (`TABLE["k"]`,
`FS[0]`, per key when the key is a constant), the target of a loop over such a list, a call of a def whose
every return is a function, and a parameter annotated `Callable[...]` or whose every call site passes a
function.  A value that is not a function keeps the string lowering, so `re.sub(P, some_str, s)` is
untouched.

Two things beyond the crash:

* a bound method as `repl` is refused by name at build time with the lambda spelling that works, instead of
  failing at run time on `AttributeError: 'R' object has no attribute 'fmt'`;
* `count < 0` replaced everything; CPython replaces nothing (`re.sub("a", "b", "aaa", -1)` is `"aaa"`).
  Fixed in `relib` for all three generated sub helpers, str and bytes.

Tests: `AIL_CURRENT/test_ail_resub2.py` (8 tests: the callable forms on both builds, the string forms on
both builds, the two refusals, and two tests of the lowering itself without building).  Probes in
`/tmp/probes/p0..p42` through `~/tools/cmp.sh`.  Differences: `DIFFERENCES.md`
C?-job-resub2-10220600-1..3.
