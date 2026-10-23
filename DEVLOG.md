# DEVLOG

## 2026-10-23 - keys-only mappings in dict() (job-pre25-10240322)

A class that implements the mapping protocol with `keys()` and `__getitem__` but no
`__iter__` was fed to the general path's pair iterator: `dict(m)` raised
`TypeError: 'instance' object is not iterable` instead of using `keys()` (CPython
`{'a': 1}`). The same argument also made `dict.update(m)` and
`defaultdict(factory, m)` take the wrong protocol, and a class whose `keys()` and
`__iter__` disagree was built from `__iter__`.

`dunderrt.py` now installs a class's `keys` method in its runtime method table and
patches `ail_dict_update_pairs` to use the mapping protocol (`keys()` then `m[k]`)
when it is present, including CPython's non-iterable-keys message. A missing
`__getitem__` reports the object's class name, not `instance`. Verified with
`bash ~/tools/cmp.sh` on six probes (basic, key/return types, keys/iter
disagreement, mapping through an argument/list item/attribute/dict value, errors,
inheritance and generator keys) and with `test_ail_pre25`.

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
