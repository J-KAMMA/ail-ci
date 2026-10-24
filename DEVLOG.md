# DEVLOG

## 2026-10-24 - pre47 review: folded INT64_MIN in the pipeline emitter (job-pre47-10241039)

The fold pass ran before `to_pipeline_c` too, but `pyfront._c_expr` emitted a folded INT64_MIN as
`ck_neg(9223372036854775808)`, which traps at run time; the earlier fix only taught `pyboxed`,
`pyboxed2` and `pyfunc` the unary spelling. `_c_expr` now emits the same
`(-9223372036854775807LL - 1)` two's-complement form, so `sum((-2**63) for x in xs)` and its
variants answer `-9223372036854775808` instead of `integer overflow`. Out-of-range constants in a
pipeline expression are still refused by name. Probes covered the negated power, `x + (-2**63)`,
`-1 << 63`, `max`, guarded folds, the direct spelling, a sum over empty input, INT64_MAX, strict
and unchecked builds, and refusals; all matched CPython or were refused by name.

## 2026-10-24 - pre47: constant integer expressions (job-pre47-10241039)

`-(-2)**63` is exactly 2**63 in CPython; the compiler emitted the fitting inner `(-2)**63` and
negated it at run time, where the checked arithmetic stopped with `integer overflow`.
`pyfront.fold_int_constants` now evaluates purely constant integer expressions before either code
path, replaces an in-range result with one int64 literal, and refuses an out-of-range result by
name with its source line. The same pass makes `-2**63` and `2**63-1` single literals instead of
arithmetic that could overflow before the outer expression. The general emitters also accept
INT64_MIN as the unary spelling `-9223372036854775808` rather than refusing its positive operand.
The refusal is `a constant integer expression overflows int64: ... 64-bit signed integer ...` on
the default and general builds.

The mandatory probes covered `-(-2)**63`, `2**63`, `10**40`, `1<<63`, the composite
`(2**70)//(2**5)`, `2**10000`, and values passed through an argument, a list item, an attribute
and a dict; every in-range program matched CPython and every out-of-range one was refused by name
on both builds. The known variable cases still differ: `a=10; a**40` and `pow(10,40)` stop at run
time with `integer overflow`. `test_ail_pre47.py` adds the first case and the boundaries above.

## 2026-10-23 - C compiler step cache (job-ctime3-10232149)

The base export already contains the content-addressed `cc` layer in
`AIL_CURRENT/python/pkg-v12/buildcache.py` (`buildcache.run_cc`, activated by `--cache`, stored under
`$AIL_CACHE` / `~/.cache/ail`, off with `AIL_NO_CACHE=1` or `--no-cache`). The task says not to add
a second cache when one already exists, so this job verifies and measures that layer and adds a
regression test for the exact reuse case:

* `test_changed_source_with_the_same_generated_c_hits_the_cc_cache` changes a typed local's name,
  which changes the merged source text (a new front-end entry) but not the generated C: the C
  compiler step is skipped and the executable is byte-identical.

Measurement on this 4-core runner, gcc 13.3, median of 5 runs, `AIL_CACHE` in a temporary
directory. "before" is `AIL_NO_CACHE=1`; "after" is a cache warm from the same C text with a new
front-end key (a renamed local), so the front end runs but the C compiler step hits. Wall time is
the whole `ail_chatgpt.py compile`; C time is the sum of the compiler wrapper's own runs (after
includes the cache's one-time toolchain probes).

| gdev program | wall before | C before | wall after | C after | outputs |
| --- | ---: | ---: | ---: | ---: | --- |
| g00_000 | 1.245 s | 0.241 s | 1.177 s | 0.013 s | identical |
| g00_002 | 1.427 s | 0.393 s | 1.186 s | 0.012 s | identical |
| g00_004 | 2.540 s | 1.418 s | 1.279 s | 0.012 s | identical |

Output SHA-256 values were equal for every before/after pair. With an unchanged source the whole
front-end cache also hits, so the compiler step is not run at all.
# Devlog

## 2026-10-22

* fuzz21 (unpacking): the general path's `UNPACK_SEQUENCE` errors now use CPython's wording and
  counts -- `too many values to unpack (expected N)`, `not enough values to unpack (expected N, got M)`,
  `(expected at least N, got M)` for a starred target, and `cannot unpack non-iterable X object`.
  Added `AIL_CURRENT/test_ail_fuzz21.py` and registered it in `ail_check.MODULES`.
## 2026-10-23 - fuzz45: float // and % use CPython's float_divmod

The general path's boxed operators and the unified pass emitted `floor(a / b)` for float `//` and a
bare `fmod` for float `%`.  `1.0 // 0.1` was 10.0 (CPython 9.0), `-0.0 % 2.0` was -0.0 (CPython
0.0), `-5.0 // inf` was -0.0 (CPython -1.0) and `inf // 2.0` was inf (CPython nan).  Both now use
one CPython float_divmod helper, so `//`, `%` and `divmod` agree, including zero-remainder signs,
infinities and NaNs.  Added `test_ail_fuzz45.py` (5 programs, two builds each).
## 2026-10-22

- job-fuzz39-10230820 (review fix): a name whose bindings mix a tuple and a number is no longer treated as a known
  tuple for the number check, so `x = (1,); x = 2.5; z = 2.5; x is z` is refused with C115 again instead of printing
  False. The `is(` spelling no longer bypasses the refusal in `numidentity.py` / `pyboxed2.py` (text gate is a word
  match, not the literal `' is '`). Added both cases to `test_ail_fuzz39.py`.
- job-fuzz39-10230820: `is` / `is not` with an equal tuple constant (including one passed to both parameters of a
  generic function) is refused by name instead of answering False where CPython answers True. Added
  `AIL_CURRENT/test_ail_fuzz39.py` and extended `numidentity.py`; `tuplib.py` leaves such a comparison for the refusal.
## 2026-10-23 - fuzz43: str.startswith/endswith tuple member type names

A non-str member of a tuple passed to `str.startswith`/`str.endswith` raised the right
`TypeError` but named the runtime tag rather than the member's class: a bytes member printed
`not instance` where CPython prints `not bytes`, and a user-class member was flattened to
`instance` too. The message now resolves the member object's class name (the prelude bytes class
or the user class) on both builds. Added `test_ail_fuzz43.py`, which also keeps valid tuples,
short-circuiting before a later bad member, empty receivers and windowed calls compared with
CPython. Other observed differences, not fixed here: `bytes.__contains__` with a str item and
bytes search with wrong-type bounds still print different TypeError text (different causes);
the non-ASCII `lower`/`upper` limit remains a documented pre-existing difference.
