# DEVLOG

## 2026-10-23 - any/all generator expressions stop at the decisive element (job-pre13-10240022)

The general path's fused `any`/`all` generator expression walked every element even after the
answer was known, so `any(hit(log, a, b) for a, b in pairs)` called `hit` for every pair; CPython
stops at the first truthy element. The fused loops now jump to one label at that element (the same
shape as the existing `next(genexp)` fusion), so tuple/list destructuring targets, filters and
nested for-clauses all stop where CPython does. Empty and no-decisive-element sequences keep the
old result. Added `AIL_CURRENT/test_ail_pre13.py`, which builds the cases on the general path and
the default build and compares both with CPython 3.12.

The other two recorded pre-existing differences remain: a `__bool__` that raises is still
swallowed by the truth helper, and an inner generator expression used as the iterable is still
materialised eagerly.

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
