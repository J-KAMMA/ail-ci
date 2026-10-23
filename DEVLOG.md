# DEVLOG

## 2026-10-23 - f03: `int(1e300)` is refused at compile time (job-pre9-10240011)

CPython's int is unbounded, so `int(1e300)` returns an exact big integer; AIL's int is 64-bit
(SEMANTICS section 1) and the conversion instead ended the program at the int64 boundary
(`integer overflow`) on both the typed/default and general builds. The value is known at compile
time, so `int(<float literal>)` outside [-2**63, 2**63) is now refused by name in all three
emitters (`pyfunc.py`, `pyboxed2.py`, `pyboxed.py`, through `pyfront.refuse_int_float_literal`),
the same way an out-of-range integer literal already was. In-range float literals and values
arriving through arguments, lists, attributes, dicts or variables keep the ordinary conversion.

`test_ail_pre9.py` covers the refused literals (1e300, -1e300, 2**63 as a float, an infinity
literal) in default/general builds on AIL_IR=0/1, and compares in-range literal and flow results
with CPython. No `docs/spec/DIFFERENCES.md` exists in this export, so no row was added.

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
