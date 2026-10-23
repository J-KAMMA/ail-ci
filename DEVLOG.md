# DEVLOG

## 2026-10-23 - reversed(dict) (job-pre5-10240009)

The fuzz73 review's pre-existing difference reproduced on both builds: `reversed(d)` raised
`TypeError: 'dict' object is not reversible` while CPython returns the keys in reverse insertion
order. `ail_iter_reversed` now has a dict case, and the new `AIL_IT_DICT_REV_KEYS` iterator walks
the dense entry array backwards. It keeps CPython's size check on every live step
(`dictionary changed size during iteration`) and marks itself exhausted once a next past the end
has been attempted, so a later resize is not reported after StopIteration.

`test_ail_pre5.py` covers empty, one/many entries, int/str/bool/tuple/None/float keys, int64-width
and negative keys, Unicode keys, reverse order after deletion/update, values reaching the call as
an argument, a list item, an attribute and a dict value, aliasing, defaultdict, a 200-entry dict,
the typed path, and mutation (delete, add, same-size replace, clear+refill, value-only update,
empty then add, yielded-all then add, exhausted then add). It runs on the general path and on the
default build with IR 0 and 1. No DIFFERENCES file exists in this export, so no row was added.

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
