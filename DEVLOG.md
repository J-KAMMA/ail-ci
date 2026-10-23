# DEVLOG

## 2026-10-23 - Positional-only parameters on the general path (job-pre1-10240007)

The modules3 review recorded a pre-existing CPython difference: `def f(a, /, *, b=2)` (and any
other `def` with positional-only parameters) was refused by name, so `kwonly_default` matched
neither build. `pyboxed2.Compiler._register_function` now binds `posonlyargs` before `args`;
`_bind_args` and the nested-def call binder still refuse a call that passes a positional-only name
as a keyword by name, and the unified hints read the positional-only annotations too. Defaults,
`*args`/`**kwargs`, static methods and methods with positional-only parameters bind in CPython's
order. A non-positional-only program's `program.c` and `program_mix0.c` hash identically to the
base tree.

Probes (`cmp.sh`, default and `AIL_UNIFIED_FORCE=1`): 20 programs cover int/str/float/bool/None,
tuple/dict/list, empty/negative, defaults, values through arguments, list items, attributes and dict
values, aliasing, methods/static methods, nested defs and `*args`/`**kwargs`; 14 match CPython and
6 are refused by name (calls passing a positional-only name as a keyword, a missing argument, and
the pre-existing starred-call limit). New `AIL_CURRENT/test_ail_pre1.py` (4 tests); on the final
commit `test_ail_pre1`, `test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3`
pass. This CI mirror has no `DIFFERENCES` file, so no row was added.

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
