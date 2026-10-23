# DEVLOG

## 2026-10-23 - Runtime KeyError keeps its key (job-pre12-10240013)

The review of job fuzz81 listed a pre-existing difference for typed tuple-keyed containers:
a missing key in a `dict[tuple[int, int], int]` or `set[tuple[int, int]]` printed
`KeyError('(4, 5)')` with `e.args == ('(4, 5)',)`, where CPython keeps the tuple itself
(`KeyError((4, 5))`, `e.args == ((4, 5),)`). The tuple program falls back to the general path,
which raised the runtime `KeyError` with `ail_obj_repr(key)` as the message and therefore as the
argument.

* `cruntime.py` now has `ail_raise_key`, which stores the raw key in `KeyError.args[0]` while
  keeping `repr(key)` as the message. Dict lookup, `pop`, `del`, `popitem`, `set.remove` and
  `set.pop` use it; `pyboxed2.py` uses it for the augmented `d[k] += v` probe. Scalar keys on the
  general path are fixed by the same cause.
* `test_ail_pre12.py` covers tuple-keyed dict get/pop with the key coming from a literal, a
  variable, an argument, a list item, an attribute and a dict value, tuple-keyed `set.remove`,
  `discard`, `popitem`/`set.pop` on empty containers, scalar keys on the same runtime path, and
  non-raising `get`/`pop`/`setdefault`.
* Probes `pre12_scalar_types`, `pre12_tuple_types`, `pre12_sources`, `pre12_setops`,
  `pre12_dictops`, `pre12_aug`, `pre12_nonraise`, `pre12_plain` and the review cases r19/r20 match
  CPython on both builds.

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
