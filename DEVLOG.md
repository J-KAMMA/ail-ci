# DEVLOG

## 2026-10-23 - str format spec: a space sign names CPython's ValueError (job-pre18-10240245)

The first pre-existing difference recorded by the fuzz66 reviewer still reproduces on this tree:
`format('x', ' z')` raised `ValueError: Sign not allowed in string format specifier`, where CPython
says `Space not allowed in string format specifier`. The same wording bug covered every str spec
with a space sign.

`AIL_CURRENT/python/pkg-v12/safetyrt.py` now distinguishes the space flag from `+`/`-` in
`ail2f_format`'s str branch. `AIL_CURRENT/python/pkg-v12/pyboxed2.py` sends a str spec that carries
any sign to `safetyrt.FMT` instead of the core formatter, which silently ignored the flag (so
`format('x', '+')` returned `x` and `format('x', ' ')` padded it). Numeric sign flags and str specs
without a sign are unchanged.

`test_ail_pre18.py` covers the recorded case, all sign spellings, literal and computed specs,
widths/alignment, empty and non-ASCII values, values from an argument/list item/attribute/dict
value, and numeric sign formatting on both builds. It and `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3` pass on the final commit.

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
