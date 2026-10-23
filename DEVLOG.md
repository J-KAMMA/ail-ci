# DEVLOG

## 2026-10-23 - Counter equality review fixes (job-pre17-10240052)

The review found two defects in the previous Counter equality branch. Counts whose `==` is
identity-based (function, class, range, instance) compared False to themselves whenever the
comparison reached the runtime directly instead of the collib helper (`same(c, c)`, a list item,
a dict value, an attribute); the branch now falls back to `ail_identical` for non-float counts,
while a NaN count still never equals itself. A self-referential count (`c["a"] = c; c == c`)
recursed until the C stack overflowed; the recursion is now bounded and traps with
`recursion depth exceeded` (exit 1, empty stdout), matching CPython's RecursionError probe.
`test_ail_pre17.py` now covers the opaque contexts, distinct identity counts, and the cycle on
both builds.

## 2026-10-23 - Counter equality (job-pre17-10240052)

The first pre-existing difference from job `fuzz64` that still reproduced here was `p1_identity`:
`Counter` with a NaN count compared to itself returned True, while CPython returns False. CPython's
`Counter.__eq__` compares every count with `==` (no whole-mapping identity shortcut, so a NaN never
equals even the same object) and treats a missing count as zero. The general runtime's dict
equality now has a Counter branch with those rules; plain dict, list and tuple identity semantics
are unchanged. `test_ail_pre17.py` covers NaN counts (self, copy, fresh, argument/list/dict/attribute
aliases) and missing/zero, negative, float and bool counts on both builds. The other recorded
differences (`p14`, `p15`, `p16`) were left untouched.

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
