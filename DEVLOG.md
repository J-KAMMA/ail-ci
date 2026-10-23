# DEVLOG

## 2026-10-23 - pre7: refuse `del` with an out-of-int64 constant index (job-pre7-10240010)

`q14` (`del a[2**63]`) was the first of the three recorded pre-existing differences that still
differed on this tree: both builds computed `2**63` at run time and trapped `integer overflow`,
where CPython raises `IndexError: cannot fit 'int' into an index-sized integer` before the delete.
An AIL int is int64, so the index cannot be represented. `pyfront.refuse_out_of_range_delete_index`
now evaluates a constant integer index (`2**63`, `10**19`, `-2**63-1`, ...) and refuses the
`del` by name at compile time on both the typed path (`pyfunc.py`) and the general path
(`pyboxed2.py`); it applies through a name, a list item, an attribute and a dict value. In-range
constant indexes are untouched, and the C runtime has no change (no hot code touched).

`q26` and `q39` are still different and were not touched.

Tests on this commit: `test_ail_pre7` (new, both builds), `test_ail_safetynet`,
`test_ail_files`, `test_ail_corpus_findings3`; `update_manifest.py --check` and
`ci_shards.py --check` rc 0.

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
