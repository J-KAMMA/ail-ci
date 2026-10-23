# DEVLOG

## 2026-10-23 - round() ndigits on the general path (job-pre10-10240012)

`round()` read `ndigits` through the union's integer member before its type checks. A missing
value or `None` therefore became 0, `round(2.5, None)` produced `2.0` instead of CPython's
`2`, and `round(2.5, 1.5)` or `round(2.5, "1")` silently rounded instead of raising
`TypeError: 'float'/'str' object cannot be interpreted as an integer`. An `__index__` instance
in that position passed the old int member by accident (right for `I()` only when the instance
happened to store 2), so `round(1.5, I(0))` returned `1.5` instead of `2.0`.

A user `__round__` had a related one-argument form: `round(u)` and `round(u, None)` passed
`None`/0 to a `(self, ndigits)` method, so a required second parameter never raised CPython's
`U.__round__() missing 1 required positional argument: 'n'`, and a method with
`ndigits=None` saw 0 instead of None.

* `ail_bi_round_obj` keeps the raw ndigits object and validates the receiver before it; a
  missing value or `None` goes through the one-argument `ail_bi_round`, other non-integers
  raise the CPython message, and an instance is accepted through `__index__`.
* `dunderrt.py` converts an instance ndigits with `__index__` and adds a per-class
  `round0` entry so the no-ndigits call reaches the user method with no argument. Generated
  wrappers in `pyboxed2.py` encode `__round__(self)`, use a literal default as written, and
  raise the required-argument `TypeError` for `__round__(self, n)`.
* `test_ail_pre10.py` covers these cases, including values arriving through an argument, a
  list item, an attribute and a dict value, on both the general path and the default build.

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
