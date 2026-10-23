# DEVLOG

## 2026-10-23 - reversed() of a generator expression (job-pre11-10240012)

`list(reversed((x, x) for x in [1, 2, 3]))` silently printed `[(3, 3), (2, 2), (1, 1)]` because the
tuple pass hoisted the generator expression to a plain list. CPython evaluates only the outermost
iterable, then raises `TypeError: 'generator' object is not reversible` without running the element
expressions. The typed path now refuses that direct shape by name, so the default build falls back
to the general path; its `_b_reversed` evaluates the outermost iterable (including side effects),
calls `ail_iter`, and then raises the same TypeError. The same runtime path catches the error in a
`try`/`except TypeError`, and list, tuple, range and str stay reversible.

Verified with `cmp.sh` on both builds for tuple, plain, empty, conditional, two-loop, nested and
non-iterable-outer generator expressions, `try`/`except` and `try`/`finally`, plus the reversible
types. `test_ail_pre11.py`: 3 tests, 0 failed. No DIFFERENCES file is present in this export, so no
`C?-` row was added.

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
